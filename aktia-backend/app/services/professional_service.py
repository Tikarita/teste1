from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.reviews import ReviewStats
from app.schemas.stats import (
    FindingShare,
    HistoryPoint,
    Period,
    PeriodSummary,
    SummaryComparison,
)
from app.services import quality_stats, review_service
from app.services.quality_stats import StatsFilters


class ProfileProfessional(BaseModel):
    id: UUID
    full_name: str | None
    role: str | None


class ProfessionalProfile(BaseModel):
    """
    Desempenho de um profissional no período, com a comparação com o próprio
    período anterior e com a clínica inteira. `versus_clinic` é o profissional
    menos a clínica, nas mesmas regras de amostra mínima das demais estatísticas.
    """

    professional: ProfileProfessional
    period: Period
    previous_period: Period
    min_sample_size: int
    summary: PeriodSummary
    previous: PeriodSummary
    comparison: SummaryComparison
    clinic_summary: PeriodSummary
    versus_clinic: SummaryComparison
    history_granularity: str
    history: list[HistoryPoint] | None
    quality_findings: list[FindingShare] | None
    review: ReviewStats
    clinic_rejection_rate: float | None


def _can_view(current: dict, professional_id: str) -> bool:
    """Administradores e gestores veem qualquer perfil da clínica; os demais, só o próprio."""
    profile = current["profile"]
    return profile.get("role") in ("admin", "manager") or str(profile["id"]) == professional_id


def get_profile(current: dict, professional_id: UUID, filters: StatsFilters) -> ProfessionalProfile:
    clinic_id = current["clinic"]["id"]
    professional_id = str(professional_id)

    if not _can_view(current, professional_id):
        raise HTTPException(
            status_code=403,
            detail="Você só pode ver o seu próprio perfil de desempenho."
        )

    member = next(
        (m for m in quality_stats._clinic_staff(clinic_id) if str(m["id"]) == professional_id),
        None
    )

    # Profissional de outra clínica responde igual a um que não existe.
    if member is None:
        raise HTTPException(
            status_code=404,
            detail="Profissional não encontrado"
        )

    own = StatsFilters(start=filters.start, end=filters.end, professional_id=UUID(professional_id))
    clinic = StatsFilters(start=filters.start, end=filters.end)

    summary = quality_stats.get_summary(clinic_id, own)
    clinic_summary = quality_stats.get_summary(clinic_id, clinic).current
    history = quality_stats.get_history(clinic_id, own)

    return ProfessionalProfile(
        professional=ProfileProfessional(
            id=professional_id,
            full_name=member.get("full_name"),
            role=member.get("role")
        ),
        period=summary.period,
        previous_period=summary.previous_period,
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        summary=summary.current,
        previous=summary.previous,
        comparison=summary.comparison,
        clinic_summary=clinic_summary,
        versus_clinic=quality_stats._compare(summary.current, clinic_summary),
        history_granularity=history.granularity,
        history=history.points,
        quality_findings=quality_stats.get_findings(clinic_id, own).items,
        review=review_service.get_review_stats(clinic_id, own),
        clinic_rejection_rate=review_service.get_review_stats(clinic_id, clinic).rejection_rate
    )
