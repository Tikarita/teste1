from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.stats import AppliedFilters, Period


ReviewVerdict = Literal["adequate", "inadequate"]

# Os mesmos valores aceitos pela constraint radiograph_reviews_reasons_check.
ReviewReason = Literal[
    "sharpness", "exposure", "contrast", "positioning",
    "noise", "artifacts", "coverage", "framing", "other"
]


class ReviewCreate(BaseModel):
    verdict: ReviewVerdict
    repeated: bool = False
    reasons: list[ReviewReason] = Field(default_factory=list, max_length=9)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _consistent(self):
        self.reasons = list(dict.fromkeys(self.reasons))

        if self.verdict == "inadequate" and not self.reasons:
            raise ValueError("Informe pelo menos um motivo para um exame inadequado.")

        if self.verdict == "adequate" and (self.reasons or self.repeated):
            raise ValueError("Um exame adequado não tem motivo de rejeição nem repetição.")

        return self


class Review(BaseModel):
    id: UUID
    radiograph_id: UUID
    analysis_id: UUID | None
    reviewed_by: UUID | None
    reviewed_by_name: str | None
    verdict: ReviewVerdict
    repeated: bool
    reasons: list[str]
    notes: str | None
    created_at: datetime


class ReasonShare(BaseModel):
    reason: str
    label: str
    count: int
    percentage: float


class ReviewStats(BaseModel):
    """
    Indicadores da revisão humana das radiografias enviadas no período.
    Contagens vêm sempre; taxas ficam nulas (com insufficient_data) quando há
    menos revisões que a amostra mínima.
    """

    uploaded: int
    reviewed: int
    coverage_rate: float | None
    human_adequate: int
    human_inadequate: int
    repeated: int
    rejection_rate: float | None
    repeat_rate: float | None
    compared_with_ai: int
    agreed_with_ai: int
    ai_agreement_rate: float | None
    ai_missed: int
    ai_false_alarm: int
    reasons: list[ReasonShare] | None
    insufficient_data: bool


class ReviewStatsResponse(ReviewStats):
    period: Period
    filters: AppliedFilters
    min_sample_size: int
