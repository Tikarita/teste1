from datetime import date, timedelta

from fastapi import HTTPException

from app.core.config import settings
from app.schemas.reports import (
    QualityReport,
    QualityReportData,
    ReportAuthor,
    ReportClinic,
    ReportModel,
    ReportSummary,
    ReportVolume,
)
from app.schemas.stats import Period
from app.services import quality_stats, review_service
from app.services.supabase_service import execute_with_retry, supabase


QUALITY_REPORT_TYPE = "quality"

# Texto fixo que acompanha todo relatório. Fica gravado junto com os números
# para o documento continuar dizendo com que método eles foram obtidos, mesmo
# que o sistema mude depois. Os percentuais do classificador são os medidos no
# conjunto de teste do treino (ver efficientnet_service.classify_adequacy).
METHODOLOGY = [
    "Este relatório registra a avaliação automatizada da qualidade técnica das radiografias "
    "enviadas à plataforma no período, como evidência de execução do Programa de Garantia da "
    "Qualidade (RDC ANVISA nº 611/2022, arts. 5º, 17, 24, 39 e 40).",
    "Cada radiografia é classificada como adequada ou inadequada por um modelo de inteligência "
    "artificial (EfficientNet-B0). O score é a probabilidade de adequação estimada pelo modelo, "
    "de 0 a 100; a imagem é considerada inadequada abaixo de 50.",
    "Limitação: no conjunto de teste o modelo acertou 77,9% das classificações e identificou "
    "58,9% das imagens inadequadas. Ele deixa de apontar parte das imagens ruins, então a taxa "
    "de inadequadas deste relatório é uma triagem, não a taxa real de rejeição do serviço.",
    "A seção de revisão registra a decisão do profissional da clínica sobre cada exame. A taxa "
    "de rejeição ali apresentada considera somente os exames revisados; a cobertura indica que "
    "parcela dos exames do período passou por essa revisão.",
    "A plataforma não apresenta notas automáticas por critério (nitidez, contraste, exposição): "
    "testadas contra as imagens rotuladas, essas métricas não se relacionaram com a adequação. Os "
    "motivos de rejeição deste relatório vêm exclusivamente da revisão dos profissionais.",
    "Este relatório não substitui os testes de aceitação e de controle de qualidade dos "
    "equipamentos previstos no Anexo I da IN ANVISA nº 94/2021, nem a avaliação do responsável "
    "técnico.",
]


def _title(start: date, end: date) -> str:
    return f"Relatório de Garantia da Qualidade — {start:%d/%m/%Y} a {end:%d/%m/%Y}"


def _insert_report(row: dict) -> dict:
    response = supabase.table("reports").insert(row).execute()
    return response.data[0]


def _select_reports(clinic_id: str, report_id: str | None = None) -> list[dict]:
    query = (
        supabase
        .table("reports")
        .select("*")
        .eq("clinic_id", str(clinic_id))
        .eq("report_type", QUALITY_REPORT_TYPE)
    )

    if report_id is not None:
        query = query.eq("id", str(report_id))

    return execute_with_retry(query.order("created_at", desc=True)).data or []


def _author_name(row: dict) -> str | None:
    return ((row.get("data") or {}).get("generated_by") or {}).get("full_name")


def _to_summary(row: dict) -> ReportSummary:
    return ReportSummary(
        id=row["id"],
        report_type=row["report_type"],
        title=row.get("title"),
        period_start=row.get("period_start"),
        period_end=row.get("period_end"),
        created_at=row["created_at"],
        generated_by_name=_author_name(row)
    )


def _to_report(row: dict) -> QualityReport:
    return QualityReport(
        **_to_summary(row).model_dump(),
        notes=row.get("notes"),
        data=row["data"]
    )


def build_quality_report_data(current: dict, start: date, end: date) -> QualityReportData:
    """Monta o conteúdo do relatório a partir das mesmas agregações do Dashboard."""
    clinic = current["clinic"]
    profile = current["profile"]
    clinic_id = clinic["id"]

    filters = quality_stats.resolve_filters("custom", start, end, None, None)
    window = {
        "p_clinic_id": str(clinic_id),
        "p_start": filters.start.isoformat(),
        "p_end": filters.end.isoformat()
    }

    summary = quality_stats.get_summary(clinic_id, filters)
    history = quality_stats.get_history(clinic_id, filters)
    professionals = quality_stats.get_by_professional(clinic_id, filters)

    volume_rows = quality_stats._rpc("report_volume", window)
    volume = volume_rows[0] if volume_rows else {}
    uploaded = int(volume.get("uploaded") or 0)
    analyzed = int(volume.get("analyzed") or 0)

    return QualityReportData(
        clinic=ReportClinic(name=clinic["name"], cnpj=clinic.get("cnpj")),
        generated_by=ReportAuthor(id=profile["id"], full_name=profile.get("full_name")),
        period=Period(start=filters.start, end=filters.end),
        previous_period=summary.previous_period,
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        volume=ReportVolume(
            uploaded=uploaded,
            analyzed=analyzed,
            not_analyzed=uploaded - analyzed
        ),
        summary=summary.current,
        previous=summary.previous,
        comparison=summary.comparison,
        history_granularity=history.granularity,
        history=history.points,
        professionals=professionals.professionals,
        quality_findings=None,
        quality_findings_discontinued=True,
        review=review_service.get_review_stats(clinic_id, filters),
        models=[
            ReportModel(model_version=row["model_version"], total=int(row["total"]))
            for row in quality_stats._rpc("report_models", window)
        ],
        methodology=METHODOLOGY
    )


def create_quality_report(
    current: dict,
    start: date,
    end: date,
    notes: str | None
) -> QualityReport:
    """Emite o relatório: calcula os números do período e grava a cópia congelada."""
    if current["profile"].get("role") not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores e gestores da clínica podem emitir relatórios."
        )

    if end > date.today() + timedelta(days=1):
        raise HTTPException(
            status_code=400,
            detail="O período do relatório não pode terminar no futuro."
        )

    data = build_quality_report_data(current, start, end)
    notes = (notes or "").strip() or None

    row = _insert_report({
        "clinic_id": str(current["clinic"]["id"]),
        "generated_by": str(current["profile"]["id"]),
        "report_type": QUALITY_REPORT_TYPE,
        "title": _title(start, end),
        "period_start": data.period.start.isoformat(),
        "period_end": data.period.end.isoformat(),
        "notes": notes,
        "data": data.model_dump(mode="json")
    })

    return _to_report(row)


def list_quality_reports(clinic_id: str) -> list[ReportSummary]:
    return [_to_summary(row) for row in _select_reports(clinic_id)]


def get_quality_report(clinic_id: str, report_id: str) -> QualityReport:
    rows = _select_reports(clinic_id, report_id)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Relatório não encontrado"
        )

    return _to_report(rows[0])
