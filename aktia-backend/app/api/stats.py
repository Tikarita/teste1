from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user
from app.schemas.stats import (
    AnalysisStatus,
    ClinicalFindingsResponse,
    FindingsResponse,
    Granularity,
    HistoryResponse,
    PeriodPreset,
    ProfessionalsResponse,
    SummaryResponse,
)
from app.schemas.reviews import ReviewStatsResponse
from app.services import finding_validation_service, professional_service, quality_stats, review_service
from app.services.finding_validation_service import DetectorStatsResponse
from app.services.professional_service import ProfessionalProfile


router = APIRouter(
    prefix="/stats",
    tags=["Stats"]
)


def get_filters(
    period: PeriodPreset = Query("30", description="Últimos 7, 30 ou 90 dias, ou 'custom' com start e end."),
    start: date | None = Query(None, description="Primeiro dia do período personalizado."),
    end: date | None = Query(None, description="Último dia (incluso) do período personalizado."),
    professional_id: UUID | None = Query(None),
    status: AnalysisStatus | None = Query(None)
) -> quality_stats.StatsFilters:
    return quality_stats.resolve_filters(period, start, end, professional_id, status)


# A clínica vem sempre do usuário autenticado: nenhuma destas rotas aceita
# clinic_id no request.

@router.get("/summary", response_model=SummaryResponse)
def summary(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return quality_stats.get_summary(current["clinic"]["id"], filters)


@router.get("/history", response_model=HistoryResponse)
def history(
    granularity: Granularity | None = Query(None, description="Padrão: dia até 31 dias, semana acima disso."),
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return quality_stats.get_history(current["clinic"]["id"], filters, granularity)


# Descontinuado: os critérios automáticos de imagem que alimentavam esta rota
# não se sustentaram na validação (ver analysis_service.IMAGE_MEASUREMENTS) e
# não são mais gravados. A rota segue respondendo com o que já estava no banco;
# para motivos de rejeição, use /stats/reviews.
@router.get("/findings", response_model=FindingsResponse, deprecated=True)
def findings(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return quality_stats.get_findings(current["clinic"]["id"], filters)


@router.get("/professionals", response_model=ProfessionalsResponse)
def professionals(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return quality_stats.get_by_professional(current["clinic"]["id"], filters)


@router.get("/clinical-findings", response_model=ClinicalFindingsResponse)
def clinical_findings(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return quality_stats.get_clinical_findings(current["clinic"]["id"], filters)


@router.get("/reviews", response_model=ReviewStatsResponse)
def reviews(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    stats = review_service.get_review_stats(current["clinic"]["id"], filters)

    return ReviewStatsResponse(
        **stats.model_dump(),
        period={"start": filters.start, "end": filters.end},
        filters={"professional_id": filters.professional_id, "status": None},
        min_sample_size=quality_stats.settings.STATS_MIN_SAMPLE_SIZE
    )


# O parâmetro de rota não pode se chamar professional_id: esse nome já é o
# filtro de query de get_filters.
@router.get("/professionals/{member_id}", response_model=ProfessionalProfile)
def professional_profile(
    member_id: UUID,
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return professional_service.get_profile(current, member_id, filters)


@router.get("/detector", response_model=DetectorStatsResponse)
def detector(
    filters: quality_stats.StatsFilters = Depends(get_filters),
    current=Depends(get_current_user)
):
    return finding_validation_service.get_detector_stats(current["clinic"]["id"], filters)
