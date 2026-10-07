from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.stats import (
    FindingShare,
    HistoryPoint,
    Period,
    PeriodSummary,
    ProfessionalStats,
    SummaryComparison,
)


class QualityReportCreate(BaseModel):
    """Período em dias inteiros, com início e fim inclusos."""

    period_start: date
    period_end: date
    notes: str | None = Field(default=None, max_length=5000)


class ReportClinic(BaseModel):
    name: str
    cnpj: str | None


class ReportAuthor(BaseModel):
    id: UUID
    full_name: str | None


class ReportVolume(BaseModel):
    uploaded: int
    analyzed: int
    not_analyzed: int


class ReportModel(BaseModel):
    # "model_" é prefixo reservado do Pydantic; aqui é o nome da coluna do banco.
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    total: int


class QualityReportData(BaseModel):
    """
    Conteúdo congelado no momento da emissão. Segue as mesmas regras das
    estatísticas: null + insufficient_data quando falta amostra, nunca zero.
    """

    clinic: ReportClinic
    generated_by: ReportAuthor
    period: Period
    previous_period: Period
    min_sample_size: int
    volume: ReportVolume
    summary: PeriodSummary
    previous: PeriodSummary
    comparison: SummaryComparison
    history_granularity: str
    history: list[HistoryPoint] | None
    professionals: list[ProfessionalStats]
    quality_findings: list[FindingShare] | None
    models: list[ReportModel]
    methodology: list[str]


class ReportSummary(BaseModel):
    id: UUID
    report_type: str
    title: str | None
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime
    generated_by_name: str | None


class QualityReport(ReportSummary):
    notes: str | None
    data: QualityReportData
