from fastapi import HTTPException

from app.core.config import settings
from app.schemas.reviews import ReasonShare, Review, ReviewCreate, ReviewStats
from app.services import quality_stats
from app.services.quality_stats import CATEGORY_LABELS, StatsFilters
from app.services.supabase_service import execute_with_retry, supabase


REASON_LABELS = {**CATEGORY_LABELS, "artifacts": "Artefatos", "other": "Outro motivo"}


def _record_review(params: dict) -> dict:
    response = supabase.rpc("record_review", params).execute()
    return response.data


def _current_review_row(radiograph_id: str, clinic_id: str) -> dict | None:
    rows = execute_with_retry(
        supabase
        .table("radiograph_reviews")
        .select("*")
        .eq("radiograph_id", str(radiograph_id))
        .eq("clinic_id", str(clinic_id))
        .eq("is_current", True)
        .limit(1)
    ).data

    return rows[0] if rows else None


def create_review(radiograph_id: str, payload: ReviewCreate, current: dict) -> Review:
    """Registra a decisão do profissional logado sobre a radiografia."""
    try:
        row = _record_review({
            "p_radiograph_id": str(radiograph_id),
            "p_clinic_id": str(current["clinic"]["id"]),
            "p_reviewed_by": str(current["profile"]["id"]),
            "p_verdict": payload.verdict,
            "p_repeated": payload.repeated,
            "p_reasons": payload.reasons,
            "p_notes": (payload.notes or "").strip() or None
        })
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"A revisão não pôde ser salva: {error}"
        )

    return Review(**row)


def get_current_review(radiograph_id: str, clinic_id: str) -> Review | None:
    row = _current_review_row(radiograph_id, clinic_id)
    return Review(**row) if row else None


def _rate(count: int, total: int) -> float:
    return round(100 * count / total, 1)


def get_review_stats(clinic_id: str, filters: StatsFilters) -> ReviewStats:
    """
    Taxa de rejeição segundo a revisão humana. O período se refere à data de
    envio da radiografia; o filtro por status da IA não se aplica.
    """
    params = quality_stats._base_params(clinic_id, filters)
    params.pop("p_status")

    rows = quality_stats._rpc("review_summary", params)
    row = rows[0] if rows else {}
    counts = {key: int(row.get(key) or 0) for key in (
        "uploaded", "reviewed", "human_adequate", "human_inadequate", "repeated",
        "compared_with_ai", "agreed_with_ai", "ai_missed", "ai_false_alarm"
    )}

    reviewed = counts["reviewed"]
    insufficient = reviewed < settings.STATS_MIN_SAMPLE_SIZE
    compared = counts["compared_with_ai"]

    reasons = None
    if not insufficient:
        reason_rows = quality_stats._rpc("review_reasons", params)
        total_reasons = sum(int(r["occurrences"]) for r in reason_rows)
        reasons = [
            ReasonShare(
                reason=r["reason"],
                label=REASON_LABELS.get(r["reason"], r["reason"]),
                count=int(r["occurrences"]),
                percentage=_rate(int(r["occurrences"]), total_reasons)
            )
            for r in reason_rows
        ]

    return ReviewStats(
        **counts,
        # Cobertura é quanto do período já foi revisado: vale com qualquer volume.
        coverage_rate=_rate(reviewed, counts["uploaded"]) if counts["uploaded"] else None,
        rejection_rate=None if insufficient else _rate(counts["human_inadequate"], reviewed),
        repeat_rate=None if insufficient else _rate(counts["repeated"], reviewed),
        ai_agreement_rate=(
            None if compared < settings.STATS_MIN_SAMPLE_SIZE
            else _rate(counts["agreed_with_ai"], compared)
        ),
        reasons=reasons,
        insufficient_data=insufficient
    )
