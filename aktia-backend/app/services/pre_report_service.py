from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.reports import ReportAuthor, ReportClinic
from app.services import quality_stats, report_service
from app.services.finding_labels import CLASS_LABELS, LOW_RELIABILITY_CLASSES


PRE_REPORT_TYPE = "analysis"

# O documento segue as seções recomendadas para laudos radiológicos pela
# European Society of Radiology ("Good practice for radiological reporting",
# 2011) e pelo American College of Radiology ("Practice Parameter for
# Communication of Diagnostic Imaging Findings"): identificação, indicação
# clínica, técnica (com as limitações do exame), achados, comparação,
# impressão e validação por assinatura. O que o sistema não sabe (indicação,
# solicitante, impressão diagnóstica) é informado por quem emite ou fica
# declarado como não informado: nada disso é preenchido pela IA.
DEFAULT_EXAM_TYPE = "Radiografia panorâmica"

# As duas diretrizes pedem o mesmo conteúdo, com ordem e títulos diferentes.
# O formato escolhido na emissão fica gravado; a tela permite ver o outro.
ReportFormat = Literal["esr", "acr"]

# Texto fixo gravado em todo pré-laudo. Os números do detector são os medidos
# no conjunto de teste do treino (ver yolo_service.detect_findings).
DISCLAIMER = [
    "Pré-laudo de apoio ao diagnóstico. Não é laudo e não substitui a avaliação clínica e "
    "radiográfica do cirurgião-dentista responsável.",
    "Os achados foram sugeridos por um modelo de inteligência artificial (YOLOv8) e constam "
    "deste documento apenas os que o profissional confirmou. O modelo erra e deixa de detectar "
    "achados com frequência (mAP50 de 0,537 no conjunto de teste): a ausência de um achado "
    "neste documento não significa que ele não exista.",
    "Os nomes dos tipos de achado seguem um mapeamento provisório das siglas do conjunto de "
    "treino e devem ser conferidos pelo profissional.",
]


class PreReportCreate(BaseModel):
    radiograph_id: UUID
    report_format: ReportFormat = "esr"
    exam_type: str = Field(default=DEFAULT_EXAM_TYPE, min_length=2, max_length=120)
    requested_by: str | None = Field(default=None, max_length=200)
    clinical_indication: str | None = Field(default=None, max_length=2000)
    # Interpretação do cirurgião-dentista. Nunca é gerada pelo sistema.
    impression: str | None = Field(default=None, max_length=5000)
    # Recomendações e observações.
    notes: str | None = Field(default=None, max_length=5000)


class PreReportExam(BaseModel):
    radiograph_id: UUID
    file_name: str
    patient_code: str | None
    uploaded_at: datetime
    professional_name: str | None


class PreReportReferral(BaseModel):
    exam_type: str = DEFAULT_EXAM_TYPE
    requested_by: str | None = None
    clinical_indication: str | None = None


class PreReportQuality(BaseModel):
    # "model_" é prefixo reservado do Pydantic; aqui é o nome da coluna do banco.
    model_config = ConfigDict(protected_namespaces=())

    ai_is_adequate: bool | None
    ai_score: float | None
    model_version: str | None
    review_verdict: str | None
    review_by: str | None
    review_reasons: list[str] = []


class PreReportFinding(BaseModel):
    """`number` é o rótulo do achado na imagem e na tabela do documento."""

    number: int
    class_code: str
    label: str
    low_reliability: bool
    confidence: float
    bbox: dict
    validated_by_name: str | None


class PreReportGroup(BaseModel):
    class_code: str
    label: str
    count: int
    numbers: list[int]


class PreReportData(BaseModel):
    """Conteúdo congelado na emissão."""

    clinic: ReportClinic
    issued_by: ReportAuthor
    exam: PreReportExam
    # Ausentes nos pré-laudos emitidos antes de o documento seguir a estrutura padrão.
    report_format: ReportFormat = "esr"
    referral: PreReportReferral = PreReportReferral()
    exam_metadata: dict | None = None
    impression: str | None = None
    quality: PreReportQuality
    detector_model: str | None
    findings: list[PreReportFinding]
    groups: list[PreReportGroup]
    detected_count: int
    discarded_count: int
    disclaimer: list[str]


class PreReportSummary(BaseModel):
    id: UUID
    title: str | None
    radiograph_id: UUID | None
    created_at: datetime
    issued_by_name: str | None


class PreReport(PreReportSummary):
    notes: str | None
    data: PreReportData


def _source(radiograph_id: str, clinic_id: str) -> dict | None:
    rows = quality_stats._rpc("pre_report_source", {
        "p_radiograph_id": str(radiograph_id),
        "p_clinic_id": str(clinic_id)
    })
    return rows[0]["source"] if rows else None


def _to_summary(row: dict) -> PreReportSummary:
    return PreReportSummary(
        id=row["id"],
        title=row.get("title"),
        radiograph_id=row.get("radiograph_id"),
        created_at=row["created_at"],
        issued_by_name=((row.get("data") or {}).get("issued_by") or {}).get("full_name")
    )


def _to_pre_report(row: dict) -> PreReport:
    return PreReport(**_to_summary(row).model_dump(), notes=row.get("notes"), data=row["data"])


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def build_data(source: dict, current: dict, payload: PreReportCreate) -> PreReportData:
    radiograph = source["radiograph"]
    analysis = source.get("analysis")
    yolo = (analysis or {}).get("yolo") or {}

    if not analysis or yolo.get("available") is not True:
        raise HTTPException(
            status_code=400,
            detail="Este exame ainda não tem pré-laudo: analise a radiografia primeiro."
        )

    detected = yolo.get("findings") or []
    decisions = {item["finding_index"]: item for item in source.get("validations") or []}

    pending = [index for index in range(len(detected)) if index not in decisions]
    if pending:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Faltam {len(pending)} achado(s) por validar. Confirme ou descarte todos "
                "antes de emitir o pré-laudo."
            )
        )

    findings: list[PreReportFinding] = []
    for index, finding in enumerate(detected):
        if decisions[index]["decision"] != "confirmed":
            continue
        code = finding["class_code"]
        findings.append(PreReportFinding(
            number=len(findings) + 1,
            class_code=code,
            label=CLASS_LABELS.get(code, code),
            low_reliability=code in LOW_RELIABILITY_CLASSES,
            confidence=finding["confidence"],
            bbox=finding["bbox"],
            validated_by_name=decisions[index].get("validated_by_name")
        ))

    groups: dict[str, PreReportGroup] = {}
    for finding in findings:
        group = groups.setdefault(finding.class_code, PreReportGroup(
            class_code=finding.class_code, label=finding.label, count=0, numbers=[]
        ))
        group.count += 1
        group.numbers.append(finding.number)

    review = source.get("review") or {}
    score = analysis.get("quality_score")

    return PreReportData(
        clinic=ReportClinic(name=current["clinic"]["name"], cnpj=current["clinic"].get("cnpj")),
        issued_by=ReportAuthor(id=current["profile"]["id"], full_name=current["profile"].get("full_name")),
        exam=PreReportExam(
            radiograph_id=radiograph["id"],
            file_name=radiograph["file_name"],
            patient_code=radiograph.get("patient_code"),
            uploaded_at=radiograph["created_at"],
            professional_name=source.get("professional_name")
        ),
        quality=PreReportQuality(
            ai_is_adequate=analysis.get("is_adequate"),
            ai_score=float(score) if score is not None else None,
            model_version=analysis.get("model_version"),
            review_verdict=review.get("verdict"),
            review_by=review.get("reviewed_by_name"),
            review_reasons=review.get("reasons") or []
        ),
        report_format=payload.report_format,
        referral=PreReportReferral(
            exam_type=payload.exam_type.strip(),
            requested_by=_text(payload.requested_by),
            clinical_indication=_text(payload.clinical_indication)
        ),
        exam_metadata=radiograph.get("exam_metadata"),
        impression=_text(payload.impression),
        detector_model=yolo.get("model"),
        findings=findings,
        groups=sorted(groups.values(), key=lambda g: (-g.count, g.label)),
        detected_count=len(detected),
        discarded_count=len(detected) - len(findings),
        disclaimer=DISCLAIMER
    )


def create(payload: PreReportCreate, current: dict) -> PreReport:
    """Emite o pré-laudo: congela os achados confirmados e a situação de qualidade do exame."""
    clinic_id = current["clinic"]["id"]
    source = _source(str(payload.radiograph_id), clinic_id)

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Radiografia não encontrada"
        )

    data = build_data(source, current, payload)
    identification = data.exam.patient_code or data.exam.file_name

    row = report_service._insert_report({
        "clinic_id": str(clinic_id),
        "generated_by": str(current["profile"]["id"]),
        "report_type": PRE_REPORT_TYPE,
        "radiograph_id": str(payload.radiograph_id),
        "title": f"Pré-laudo — {identification}",
        "notes": _text(payload.notes),
        "data": data.model_dump(mode="json")
    })

    return _to_pre_report(row)


def list_for_radiograph(clinic_id: str, radiograph_id: UUID) -> list[PreReportSummary]:
    rows = report_service._select_reports(
        clinic_id, report_type=PRE_REPORT_TYPE, radiograph_id=str(radiograph_id)
    )
    return [_to_summary(row) for row in rows]


def get(clinic_id: str, report_id: UUID) -> PreReport:
    rows = report_service._select_reports(clinic_id, str(report_id), report_type=PRE_REPORT_TYPE)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Pré-laudo não encontrado"
        )

    return _to_pre_report(rows[0])
