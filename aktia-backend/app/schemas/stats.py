from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


AnalysisStatus = Literal["approved", "attention", "rejected"]
PeriodPreset = Literal["7", "30", "90", "custom"]
Granularity = Literal["day", "week"]


class Period(BaseModel):
    """Intervalo [start, end) usado na consulta."""

    start: datetime
    end: datetime


class AppliedFilters(BaseModel):
    professional_id: UUID | None = None
    status: AnalysisStatus | None = None


class StatusRates(BaseModel):
    """Percentual (0-100) das análises do período em cada status."""

    approved: float
    attention: float
    rejected: float


class StatusCounts(BaseModel):
    """Quantidade de análises em cada status. É contagem, não estatística: vem sempre."""

    approved: int
    attention: int
    rejected: int


class PeriodSummary(BaseModel):
    total: int
    status_counts: StatusCounts
    avg_score: float | None
    status_rates: StatusRates | None
    insufficient_data: bool


class SummaryComparison(BaseModel):
    """Período atual menos o anterior. null quando um dos dois não tem dados suficientes."""

    avg_score_delta: float | None
    approved_rate_delta: float | None
    insufficient_data: bool


class SummaryResponse(BaseModel):
    period: Period
    previous_period: Period
    filters: AppliedFilters
    min_sample_size: int
    current: PeriodSummary
    previous: PeriodSummary
    comparison: SummaryComparison


class HistoryPoint(BaseModel):
    """Um dia, ou a segunda-feira que abre a semana."""

    bucket: date
    avg_score: float | None
    total: int


class HistoryResponse(BaseModel):
    period: Period
    filters: AppliedFilters
    granularity: Granularity
    min_sample_size: int
    total: int
    points: list[HistoryPoint] | None
    insufficient_data: bool


class FindingShare(BaseModel):
    category: str
    label: str
    count: int
    percentage: float


class FindingsResponse(BaseModel):
    period: Period
    filters: AppliedFilters
    min_sample_size: int
    total_analyses: int
    total_findings: int | None
    items: list[FindingShare] | None
    insufficient_data: bool


class ProfessionalStats(BaseModel):
    """professional_id e full_name nulos = radiografias sem profissional informado."""

    professional_id: UUID | None
    full_name: str | None
    total: int
    status_counts: StatusCounts
    avg_score: float | None
    approved_rate: float | None
    insufficient_data: bool


class ProfessionalsResponse(BaseModel):
    period: Period
    filters: AppliedFilters
    min_sample_size: int
    professionals: list[ProfessionalStats]


class ClinicalFindingCount(BaseModel):
    class_code: str
    label: str
    low_reliability: bool
    count: int
    analyses_with_finding: int
    percentage_of_analyses: float


class ClinicalFindingsResponse(BaseModel):
    """Achados do detector (YOLO). Só contam análises em que o detector rodou."""

    period: Period
    filters: AppliedFilters
    min_sample_size: int
    analyses_evaluated: int
    items: list[ClinicalFindingCount] | None
    insufficient_data: bool
