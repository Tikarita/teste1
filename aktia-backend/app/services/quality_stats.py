from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.config import settings
from app.schemas.stats import (
    AppliedFilters,
    ClinicalFindingCount,
    ClinicalFindingsResponse,
    FindingShare,
    FindingsResponse,
    HistoryPoint,
    HistoryResponse,
    Period,
    PeriodSummary,
    ProfessionalStats,
    ProfessionalsResponse,
    StatusCounts,
    StatusRates,
    SummaryComparison,
    SummaryResponse,
)
from app.services.finding_labels import CLASS_LABELS, LOW_RELIABILITY_CLASSES
from app.services.supabase_service import supabase


MAX_CUSTOM_PERIOD_DAYS = 366

# Até esse tamanho de período o histórico sai por dia; acima, por semana.
DAILY_HISTORY_MAX_DAYS = 31

# Categorias aceitas por analysis_findings.category (check constraint do banco).
CATEGORY_LABELS = {
    "sharpness": "Nitidez",
    "exposure": "Exposição",
    "contrast": "Contraste",
    "positioning": "Posicionamento",
    "noise": "Ruído",
    "artifacts": "Exposição/Artefatos",
    "coverage": "Cobertura anatômica",
    "framing": "Enquadramento"
}


@dataclass(frozen=True)
class StatsFilters:
    """Filtros já validados. O período é [start, end)."""

    start: datetime
    end: datetime
    professional_id: UUID | None = None
    status: str | None = None

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def previous(self) -> "StatsFilters":
        """Mesmos filtros no período imediatamente anterior, de mesma duração."""
        return StatsFilters(
            start=self.start - self.duration,
            end=self.start,
            professional_id=self.professional_id,
            status=self.status
        )


def resolve_filters(
    period: str,
    start: date | None,
    end: date | None,
    professional_id: UUID | None,
    status: str | None,
    today: date | None = None
) -> StatsFilters:
    """
    Converte os parâmetros da rota num intervalo de datas.

    Os períodos fechados (7/30/90) terminam no fim do dia de hoje, no fuso
    das estatísticas, e incluem hoje na contagem. No personalizado, `start`
    e `end` são dias inteiros e ambos entram no intervalo.
    """
    timezone = ZoneInfo(settings.STATS_TIMEZONE)

    if period == "custom":
        if start is None or end is None:
            raise HTTPException(
                status_code=400,
                detail="Informe start e end para um período personalizado."
            )

        if end < start:
            raise HTTPException(
                status_code=400,
                detail="A data final não pode ser anterior à inicial."
            )

        if (end - start).days + 1 > MAX_CUSTOM_PERIOD_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"O período personalizado pode ter no máximo {MAX_CUSTOM_PERIOD_DAYS} dias."
            )

        first_day, last_day = start, end
    else:
        last_day = today or datetime.now(timezone).date()
        first_day = last_day - timedelta(days=int(period) - 1)

    return StatsFilters(
        start=datetime.combine(first_day, time.min, tzinfo=timezone),
        end=datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=timezone),
        professional_id=professional_id,
        status=status
    )


def _rpc(function_name: str, params: dict) -> list[dict]:
    """Chama uma função de agregação do banco (quality_summary, quality_history, quality_findings)."""
    try:
        response = supabase.rpc(function_name, params).execute()
    except Exception as error:
        # O caso típico é a função ainda não existir no banco (migration de
        # supabase/migrations/ não aplicada).
        raise HTTPException(
            status_code=503,
            detail=f"Estatísticas indisponíveis: a função {function_name} falhou no banco ({error})."
        )

    return response.data or []


def _base_params(clinic_id: str, filters: StatsFilters) -> dict:
    return {
        "p_clinic_id": str(clinic_id),
        "p_start": filters.start.isoformat(),
        "p_end": filters.end.isoformat(),
        "p_professional_id": str(filters.professional_id) if filters.professional_id else None,
        "p_status": filters.status
    }


def _period(filters: StatsFilters) -> Period:
    return Period(start=filters.start, end=filters.end)


def _applied(filters: StatsFilters) -> AppliedFilters:
    return AppliedFilters(professional_id=filters.professional_id, status=filters.status)


def _rate(count: int, total: int) -> float:
    return round(100 * count / total, 1)


def _status_counts(row: dict) -> StatusCounts:
    return StatusCounts(
        approved=int(row.get("approved") or 0),
        attention=int(row.get("attention") or 0),
        rejected=int(row.get("rejected") or 0)
    )


def _period_summary(clinic_id: str, filters: StatsFilters) -> PeriodSummary:
    rows = _rpc("quality_summary", _base_params(clinic_id, filters))
    row = rows[0] if rows else {}
    total = int(row.get("total") or 0)
    counts = _status_counts(row)

    if total < settings.STATS_MIN_SAMPLE_SIZE:
        return PeriodSummary(
            total=total,
            status_counts=counts,
            avg_score=None,
            status_rates=None,
            insufficient_data=True
        )

    avg_score = row.get("avg_score")

    return PeriodSummary(
        total=total,
        status_counts=counts,
        avg_score=float(avg_score) if avg_score is not None else None,
        status_rates=StatusRates(
            approved=_rate(counts.approved, total),
            attention=_rate(counts.attention, total),
            rejected=_rate(counts.rejected, total)
        ),
        insufficient_data=False
    )


def _compare(current: PeriodSummary, previous: PeriodSummary) -> SummaryComparison:
    if current.insufficient_data or previous.insufficient_data:
        return SummaryComparison(
            avg_score_delta=None,
            approved_rate_delta=None,
            insufficient_data=True
        )

    avg_score_delta = (
        round(current.avg_score - previous.avg_score, 1)
        if current.avg_score is not None and previous.avg_score is not None
        else None
    )

    return SummaryComparison(
        avg_score_delta=avg_score_delta,
        approved_rate_delta=round(
            current.status_rates.approved - previous.status_rates.approved, 1
        ),
        insufficient_data=False
    )


def get_summary(clinic_id: str, filters: StatsFilters) -> SummaryResponse:
    previous_filters = filters.previous()

    current = _period_summary(clinic_id, filters)
    previous = _period_summary(clinic_id, previous_filters)

    return SummaryResponse(
        period=_period(filters),
        previous_period=_period(previous_filters),
        filters=_applied(filters),
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        current=current,
        previous=previous,
        comparison=_compare(current, previous)
    )


def get_history(
    clinic_id: str,
    filters: StatsFilters,
    granularity: str | None = None
) -> HistoryResponse:
    if granularity is None:
        granularity = "day" if filters.duration.days <= DAILY_HISTORY_MAX_DAYS else "week"

    rows = _rpc("quality_history", {
        **_base_params(clinic_id, filters),
        "p_granularity": granularity,
        "p_timezone": settings.STATS_TIMEZONE
    })

    total = sum(int(row["total"]) for row in rows)
    insufficient = total < settings.STATS_MIN_SAMPLE_SIZE

    points = None if insufficient else [
        HistoryPoint(
            bucket=row["bucket"],
            avg_score=float(row["avg_score"]) if row["avg_score"] is not None else None,
            total=int(row["total"])
        )
        for row in rows
    ]

    return HistoryResponse(
        period=_period(filters),
        filters=_applied(filters),
        granularity=granularity,
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        total=total,
        points=points,
        insufficient_data=insufficient
    )


def get_findings(clinic_id: str, filters: StatsFilters) -> FindingsResponse:
    """
    Distribuição dos critérios de qualidade com problema (atenção ou
    reprovado) por categoria: de todos os problemas apontados no período,
    que fatia é de nitidez, de contraste, etc.
    """
    params = _base_params(clinic_id, filters)

    summary_rows = _rpc("quality_summary", params)
    total_analyses = int(summary_rows[0].get("total") or 0) if summary_rows else 0

    if total_analyses < settings.STATS_MIN_SAMPLE_SIZE:
        return FindingsResponse(
            period=_period(filters),
            filters=_applied(filters),
            min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
            total_analyses=total_analyses,
            total_findings=None,
            items=None,
            insufficient_data=True
        )

    rows = _rpc("quality_findings", params)
    total_findings = sum(int(row["occurrences"]) for row in rows)

    return FindingsResponse(
        period=_period(filters),
        filters=_applied(filters),
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        total_analyses=total_analyses,
        total_findings=total_findings,
        items=[
            FindingShare(
                category=row["category"],
                label=CATEGORY_LABELS.get(row["category"], row["category"]),
                count=int(row["occurrences"]),
                percentage=_rate(int(row["occurrences"]), total_findings)
            )
            for row in rows
        ],
        insufficient_data=False
    )


def _clinic_staff(clinic_id: str) -> list[dict]:
    """Profissionais da clínica (id e nome), para listar também quem ainda não tem análise."""
    response = (
        supabase
        .table("profiles")
        .select("id, full_name")
        .eq("clinic_id", str(clinic_id))
        .execute()
    )
    return response.data or []


def get_by_professional(clinic_id: str, filters: StatsFilters) -> ProfessionalsResponse:
    """
    Qualidade por profissional responsável pela captura. Todo profissional da
    clínica aparece, mesmo sem análises no período; radiografias sem
    profissional informado formam uma linha própria, com nome nulo.
    O filtro por profissional não se aplica aqui.
    """
    params = _base_params(clinic_id, filters)
    params.pop("p_professional_id")

    rows = {
        str(row["professional_id"]) if row["professional_id"] else None: row
        for row in _rpc("quality_by_professional", params)
    }

    people = [(str(member["id"]), member.get("full_name")) for member in _clinic_staff(clinic_id)]
    if None in rows:
        people.append((None, None))

    professionals = []
    for professional_id, full_name in people:
        row = rows.get(professional_id, {})
        total = int(row.get("total") or 0)
        counts = _status_counts(row)
        insufficient = total < settings.STATS_MIN_SAMPLE_SIZE
        avg_score = row.get("avg_score")

        professionals.append(ProfessionalStats(
            professional_id=professional_id,
            full_name=full_name,
            total=total,
            status_counts=counts,
            avg_score=None if insufficient or avg_score is None else float(avg_score),
            approved_rate=None if insufficient else _rate(counts.approved, total),
            insufficient_data=insufficient
        ))

    # Quem tem média vem primeiro, da maior para a menor; depois por volume.
    professionals.sort(key=lambda p: (
        p.avg_score is None,
        -(p.avg_score or 0),
        -p.total,
        p.full_name or "\uffff"
    ))

    return ProfessionalsResponse(
        period=_period(filters),
        filters=AppliedFilters(professional_id=None, status=filters.status),
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        professionals=professionals
    )


def get_clinical_findings(clinic_id: str, filters: StatsFilters) -> ClinicalFindingsResponse:
    """
    Achados clínicos mais frequentes segundo o detector (YOLO), contando só as
    análises em que ele rodou de verdade. O filtro por status não se aplica.
    """
    params = _base_params(clinic_id, filters)
    params.pop("p_status")

    rows = _rpc("clinical_findings", params)
    analyses_evaluated = int(rows[0]["analyses_evaluated"]) if rows else 0
    applied = AppliedFilters(professional_id=filters.professional_id, status=None)

    if analyses_evaluated < settings.STATS_MIN_SAMPLE_SIZE:
        return ClinicalFindingsResponse(
            period=_period(filters),
            filters=applied,
            min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
            analyses_evaluated=analyses_evaluated,
            items=None,
            insufficient_data=True
        )

    return ClinicalFindingsResponse(
        period=_period(filters),
        filters=applied,
        min_sample_size=settings.STATS_MIN_SAMPLE_SIZE,
        analyses_evaluated=analyses_evaluated,
        items=[
            ClinicalFindingCount(
                class_code=row["class_code"],
                label=CLASS_LABELS.get(row["class_code"], row["class_code"]),
                low_reliability=row["class_code"] in LOW_RELIABILITY_CLASSES,
                count=int(row["occurrences"]),
                analyses_with_finding=int(row["analyses_with_finding"]),
                percentage_of_analyses=_rate(int(row["analyses_with_finding"]), analyses_evaluated)
            )
            for row in rows
            if row["class_code"] is not None
        ],
        insufficient_data=False
    )
