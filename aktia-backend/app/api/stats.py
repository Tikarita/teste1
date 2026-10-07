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
from app.services import quality_stats


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


@router.get("/findings", response_model=FindingsResponse)
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
