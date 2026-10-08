from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.stats import AppliedFilters, Period
from app.services import quality_stats
from app.services.finding_labels import CLASS_LABELS, LOW_RELIABILITY_CLASSES
from app.services.quality_stats import StatsFilters
from app.services.supabase_service import supabase


class FindingDecision(BaseModel):
    finding_index: int = Field(ge=0)
    # "pending" desfaz uma decisão já tomada.
    decision: Literal["confirmed", "discarded", "pending"]


class FindingValidationRequest(BaseModel):
    decisions: list[FindingDecision] = Field(min_length=1, max_length=500)


class FindingValidation(BaseModel):
    finding_index: int
    class_code: str
    decision: Literal["confirmed", "discarded"]
    validated_by: UUID | None
    validated_by_name: str | None
    created_at: datetime


class DetectorClassStats(BaseModel):
    class_code: str
    label: str
    low_reliability: bool
    confirmed: int
    discarded: int
    validated: int
    # Dos achados validados deste tipo, quantos % foram confirmados.
    # null abaixo da amostra mínima.
    confirmation_rate: float | None


class DetectorStatsResponse(BaseModel):
    period: Period
    filters: AppliedFilters
    min_sample_size: int
    validated: int
    confirmation_rate: float | None
    classes: list[DetectorClassStats]
    insufficient_data: bool


def _current_rows(radiograph_id: str, clinic_id: str) -> list[dict]:
    response = supabase.rpc("current_finding_validations", {
        "p_radiograph_id": str(radiograph_id),
        "p_clinic_id": str(clinic_id)
    }).execute()
    return response.data or []


def _record(params: dict) -> list[dict]:
    response = supabase.rpc("record_finding_validations", params).execute()
    return response.data or []


def get_current(radiograph_id: str, clinic_id: str) -> list[FindingValidation]:
    return [FindingValidation(**row) for row in _current_rows(radiograph_id, clinic_id)]


def save(radiograph_id: str, payload: FindingValidationRequest, current: dict) -> list[FindingValidation]:
    """Grava as decisões do profissional logado e devolve as vigentes."""
    # A última decisão do lote vale, se o mesmo achado vier repetido.
    decisions = {item.finding_index: item.decision for item in payload.decisions}

    try:
        rows = _record({
            "p_radiograph_id": str(radiograph_id),
            "p_clinic_id": str(current["clinic"]["id"]),
            "p_validated_by": str(current["profile"]["id"]),
            "p_decisions": [
                {"finding_index": index, "decision": decision}
                for index, decision in sorted(decisions.items())
            ]
        })
    except Exception as error:
        message = str(error)
        if "não existe nesta análise" in message or "sem análise" in message:
            raise HTTPException(
                status_code=400,
                detail="Achado inexistente na análise atual. Recarregue o exame: ele pode ter sido reanalisado."
            )
        raise HTTPException(
            status_code=500,
            detail=f"A validação não pôde ser salva: {error}"
        )

    return [FindingValidation(**row) for row in rows]


def _rate(count: int, total: int) -> float:
    return round(100 * count / total, 1)


def get_detector_stats(clinic_id: str, filters: StatsFilters) -> DetectorStatsResponse:
    """
    Quanto o detector de achados acerta, medido pelo que os profissionais
    confirmam ou descartam. Os filtros por profissional e status não se aplicam.
    """
    rows = quality_stats._rpc("finding_validation_stats", {
        "p_clinic_id": str(clinic_id),
        "p_start": filters.start.isoformat(),
        "p_end": filters.end.isoformat()
    })

    classes = []
    for row in rows:
        confirmed, discarded = int(row["confirmed"]), int(row["discarded"])
        validated = confirmed + discarded
        classes.append(DetectorClassStats(
            class_code=row["class_code"],
            label=CLASS_LABELS.get(row["class_code"], row["class_code"]),
            low_reliability=row["class_code"] in LOW_RELIABILITY_CLASSES,
            confirmed=confirmed,
            discarded=discarded,
            validated=validated,
            confirmation_rate=(
                None if validated < settings.STATS_MIN_SAMPLE_SIZE else _rate(confirmed, validated)
            )
        ))

    total = sum(item.validated for item in classes)
    insufficient = total < settings.STATS_MIN_SAMPLE_SIZE

    return DetectorStatsResponse(
        period=Period(start=filters.start, end=filters.end),
        filters=AppliedFilters(professional_id=None, status=None),
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        validated=total,
        confirmation_rate=None if insufficient else _rate(sum(item.confirmed for item in classes), total),
        classes=classes,
        insufficient_data=insufficient
    )
