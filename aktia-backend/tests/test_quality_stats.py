from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.services import quality_stats
from tests.conftest import TODAY, apply_migrations, local_noon


pytestmark = pytest.mark.usefixtures("rpc_on_database")


def last_days(days: str, **filters) -> quality_stats.StatsFilters:
    return quality_stats.resolve_filters(
        days, None, None,
        filters.get("professional_id"), filters.get("status"),
        today=TODAY
    )


def days_ago(count: int) -> date:
    return TODAY - timedelta(days=count)


# --- resumo -------------------------------------------------------------------

def test_summary_average_and_status_rates(seed):
    clinic = seed.clinic()
    for score, status in [(80, "approved"), (90, "approved"), (70, "approved"),
                          (60, "approved"), (50, "rejected"), (40, "attention")]:
        seed.analysis(clinic, score, status)

    current = quality_stats.get_summary(clinic, last_days("7")).current

    assert current.total == 6
    assert current.avg_score == 65.0
    assert current.status_rates.approved == 66.7
    assert current.status_rates.rejected == 16.7
    assert current.status_rates.attention == 16.7
    assert current.insufficient_data is False


def test_summary_without_data_returns_null_not_zero(seed):
    clinic = seed.clinic()

    summary = quality_stats.get_summary(clinic, last_days("30"))

    assert summary.current.total == 0
    assert summary.current.avg_score is None
    assert summary.current.status_rates is None
    assert summary.current.insufficient_data is True
    assert summary.comparison.avg_score_delta is None
    assert summary.comparison.insufficient_data is True


def test_summary_below_minimum_sample_is_insufficient(seed):
    clinic = seed.clinic()
    for score in (90, 80, 70, 60):
        seed.analysis(clinic, score)

    current = quality_stats.get_summary(clinic, last_days("7")).current

    assert current.total == 4
    assert current.avg_score is None
    assert current.insufficient_data is True


def test_summary_period_includes_today_and_excludes_older_days(seed):
    clinic = seed.clinic()
    for day in (TODAY, days_ago(1), days_ago(3), days_ago(5), days_ago(6)):
        seed.analysis(clinic, 80, day=day)
    seed.analysis(clinic, 10, day=days_ago(7))

    summary = quality_stats.get_summary(clinic, last_days("7"))

    assert summary.current.total == 5
    assert summary.current.avg_score == 80.0
    assert summary.previous.total == 1


def test_summary_compares_with_previous_period_of_same_duration(seed):
    clinic = seed.clinic()
    for score, status in [(90, "approved"), (90, "approved"), (80, "approved"),
                          (80, "approved"), (60, "rejected")]:
        seed.analysis(clinic, score, status, day=days_ago(2))
    for score, status in [(70, "approved"), (70, "approved"), (60, "rejected"),
                          (60, "rejected"), (40, "rejected")]:
        seed.analysis(clinic, score, status, day=days_ago(9))
    # Fora dos dois períodos: não pode entrar em nenhum.
    seed.analysis(clinic, 0, "rejected", day=days_ago(14))

    summary = quality_stats.get_summary(clinic, last_days("7"))

    assert summary.period.end - summary.period.start == timedelta(days=7)
    assert summary.previous_period.end == summary.period.start
    assert summary.previous_period.end - summary.previous_period.start == timedelta(days=7)

    assert summary.current.avg_score == 80.0
    assert summary.previous.total == 5
    assert summary.previous.avg_score == 60.0
    assert summary.comparison.avg_score_delta == 20.0
    assert summary.comparison.approved_rate_delta == 40.0
    assert summary.comparison.insufficient_data is False


def test_comparison_is_null_when_previous_period_is_insufficient(seed):
    clinic = seed.clinic()
    for _ in range(5):
        seed.analysis(clinic, 80, day=days_ago(1))
    seed.analysis(clinic, 50, day=days_ago(10))

    summary = quality_stats.get_summary(clinic, last_days("7"))

    assert summary.current.avg_score == 80.0
    assert summary.previous.insufficient_data is True
    assert summary.comparison.avg_score_delta is None
    assert summary.comparison.approved_rate_delta is None
    assert summary.comparison.insufficient_data is True


# --- filtros ------------------------------------------------------------------

def test_filter_by_professional(seed):
    clinic = seed.clinic()
    ana = seed.profile(clinic, "Ana")
    bruno = seed.profile(clinic, "Bruno")
    for score in (90, 90, 90, 90, 90):
        seed.analysis(clinic, score, professional_id=ana)
    for score in (50, 50, 50, 50, 50):
        seed.analysis(clinic, score, "rejected", professional_id=bruno)

    everyone = quality_stats.get_summary(clinic, last_days("7")).current
    only_ana = quality_stats.get_summary(clinic, last_days("7", professional_id=ana)).current
    only_bruno = quality_stats.get_summary(clinic, last_days("7", professional_id=bruno)).current

    assert (everyone.total, everyone.avg_score) == (10, 70.0)
    assert (only_ana.total, only_ana.avg_score) == (5, 90.0)
    assert (only_bruno.total, only_bruno.avg_score) == (5, 50.0)
    assert only_bruno.status_rates.rejected == 100.0


def test_filter_by_status(seed):
    clinic = seed.clinic()
    for score in (90, 80, 70, 60, 50):
        seed.analysis(clinic, score, "approved")
    for score in (30, 20, 10, 20, 20):
        seed.analysis(clinic, score, "rejected")

    rejected = quality_stats.get_summary(clinic, last_days("7", status="rejected")).current

    assert rejected.total == 5
    assert rejected.avg_score == 20.0
    assert rejected.status_rates.rejected == 100.0
    assert rejected.status_rates.approved == 0.0


def test_custom_period_includes_both_ends(seed):
    clinic = seed.clinic()
    for day in (date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 5), date(2026, 3, 9), date(2026, 3, 10)):
        seed.analysis(clinic, 60, day=day)
    seed.analysis(clinic, 100, day=date(2026, 2, 28))
    seed.analysis(clinic, 100, day=date(2026, 3, 11))

    filters = quality_stats.resolve_filters(
        "custom", date(2026, 3, 1), date(2026, 3, 10), None, None
    )
    summary = quality_stats.get_summary(clinic, filters)

    assert summary.current.total == 5
    assert summary.current.avg_score == 60.0
    assert summary.previous_period.end - summary.previous_period.start == timedelta(days=10)
    assert summary.previous.total == 1


@pytest.mark.parametrize("start, end", [
    (None, None),
    (date(2026, 3, 10), date(2026, 3, 1)),
    (date(2024, 1, 1), date(2026, 1, 1)),
])
def test_custom_period_rejects_invalid_ranges(start, end):
    with pytest.raises(HTTPException) as error:
        quality_stats.resolve_filters("custom", start, end, None, None)

    assert error.value.status_code == 400


# --- análises sem profissional ------------------------------------------------

def test_analyses_without_professional_count_for_the_clinic_only(seed):
    clinic = seed.clinic()
    ana = seed.profile(clinic, "Ana")
    for _ in range(5):
        seed.analysis(clinic, 90, professional_id=ana)
    for _ in range(5):
        seed.analysis(clinic, 50, "rejected", professional_id=None)

    everyone = quality_stats.get_summary(clinic, last_days("7")).current
    only_ana = quality_stats.get_summary(clinic, last_days("7", professional_id=ana)).current

    assert (everyone.total, everyone.avg_score) == (10, 70.0)
    assert (only_ana.total, only_ana.avg_score) == (5, 90.0)


# --- histórico ----------------------------------------------------------------

def test_history_by_day_skips_days_without_analyses(seed):
    clinic = seed.clinic()
    for score in (90, 70):
        seed.analysis(clinic, score, day=days_ago(3))
    for score in (60, 60, 30):
        seed.analysis(clinic, score, day=TODAY)

    history = quality_stats.get_history(clinic, last_days("7"))

    assert history.granularity == "day"
    assert history.total == 5
    assert [(p.bucket, p.avg_score, p.total) for p in history.points] == [
        (days_ago(3), 80.0, 2),
        (TODAY, 50.0, 3),
    ]


def test_history_uses_the_clinic_day_not_utc(seed):
    clinic = seed.clinic()
    # 01:00 UTC do dia 30 ainda é 22:00 do dia 29 em São Paulo.
    late_evening = datetime(2026, 6, 30, 1, 0, tzinfo=timezone.utc)
    for _ in range(5):
        seed.analysis(clinic, 80, created_at=late_evening)

    history = quality_stats.get_history(clinic, last_days("7"))

    assert [p.bucket for p in history.points] == [date(2026, 6, 29)]


def test_history_by_week_groups_from_monday(seed):
    clinic = seed.clinic()
    # 2026-06-22 e 2026-06-29 são segundas-feiras.
    for score, day in [(100, date(2026, 6, 22)), (80, date(2026, 6, 24)), (60, date(2026, 6, 28)),
                       (50, date(2026, 6, 29)), (30, date(2026, 6, 30))]:
        seed.analysis(clinic, score, day=day)

    history = quality_stats.get_history(clinic, last_days("30"), granularity="week")

    assert [(p.bucket, p.avg_score, p.total) for p in history.points] == [
        (date(2026, 6, 22), 80.0, 3),
        (date(2026, 6, 29), 40.0, 2),
    ]


def test_history_defaults_to_week_for_long_periods(seed):
    clinic = seed.clinic()

    assert quality_stats.get_history(clinic, last_days("30")).granularity == "day"
    assert quality_stats.get_history(clinic, last_days("90")).granularity == "week"


def test_history_without_enough_data_returns_null(seed):
    clinic = seed.clinic()
    seed.analysis(clinic, 80)

    history = quality_stats.get_history(clinic, last_days("7"))

    assert history.total == 1
    assert history.points is None
    assert history.insufficient_data is True


# --- achados ------------------------------------------------------------------

def test_findings_distribution_by_category(seed):
    clinic = seed.clinic()
    seed.analysis(clinic, 40, "rejected", findings={"sharpness": "rejected", "contrast": "attention"})
    seed.analysis(clinic, 45, "rejected", findings={"sharpness": "rejected", "contrast": "approved"})
    seed.analysis(clinic, 50, "rejected", findings={"sharpness": "attention", "artifacts": "rejected"})
    seed.analysis(clinic, 90, findings={"sharpness": "approved"})
    seed.analysis(clinic, 95, findings={"sharpness": "approved", "coverage": "approved"})

    findings = quality_stats.get_findings(clinic, last_days("7"))

    assert findings.total_analyses == 5
    assert findings.total_findings == 5
    assert [(i.category, i.label, i.count, i.percentage) for i in findings.items] == [
        ("sharpness", "Nitidez", 3, 60.0),
        ("artifacts", "Exposição/Artefatos", 1, 20.0),
        ("contrast", "Contraste", 1, 20.0),
    ]
    assert findings.insufficient_data is False


def test_findings_with_no_problems_is_an_empty_list_not_insufficient(seed):
    clinic = seed.clinic()
    for _ in range(5):
        seed.analysis(clinic, 90, findings={"sharpness": "approved"})

    findings = quality_stats.get_findings(clinic, last_days("7"))

    assert findings.items == []
    assert findings.total_findings == 0
    assert findings.insufficient_data is False


def test_findings_without_enough_analyses_returns_null(seed):
    clinic = seed.clinic()
    seed.analysis(clinic, 40, "rejected", findings={"sharpness": "rejected"})

    findings = quality_stats.get_findings(clinic, last_days("7"))

    assert findings.total_analyses == 1
    assert findings.items is None
    assert findings.total_findings is None
    assert findings.insufficient_data is True


# --- isolamento entre clínicas --------------------------------------------------

def test_clinic_never_sees_another_clinics_numbers(seed):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    for _ in range(5):
        seed.analysis(clinic_a, 90, findings={"contrast": "attention"})
    for _ in range(8):
        seed.analysis(clinic_b, 20, "rejected", findings={"sharpness": "rejected"})

    summary_a = quality_stats.get_summary(clinic_a, last_days("7")).current
    history_a = quality_stats.get_history(clinic_a, last_days("7"))
    findings_a = quality_stats.get_findings(clinic_a, last_days("7"))

    assert (summary_a.total, summary_a.avg_score) == (5, 90.0)
    assert history_a.total == 5
    assert [i.category for i in findings_a.items] == ["contrast"]


def test_filtering_by_another_clinics_professional_returns_nothing(seed):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    professional_b = seed.profile(clinic_b, "De outra clínica")
    for _ in range(5):
        seed.analysis(clinic_b, 20, "rejected", professional_id=professional_b)

    current = quality_stats.get_summary(
        clinic_a, last_days("7", professional_id=professional_b)
    ).current

    assert current.total == 0
    assert current.avg_score is None
    assert current.insufficient_data is True


def as_user(db, role: str, user_id: str | None = None):
    """Roda as próximas consultas como um papel do Supabase, com o auth.uid() do usuário."""
    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (user_id or "",))
    db.execute(f"set role {role}")


def test_rls_limits_rows_to_the_users_clinic(seed, db):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    for _ in range(3):
        seed.analysis(clinic_a, 90, findings={"contrast": "attention"})
    for _ in range(4):
        seed.analysis(clinic_b, 20, "rejected", findings={"sharpness": "rejected"})

    as_user(db, "authenticated", user_a)
    try:
        analyses = db.execute("select clinic_id from analyses").fetchall()
        findings = db.execute("select category from analysis_findings").fetchall()

        assert {str(row["clinic_id"]) for row in analyses} == {clinic_a}
        assert len(analyses) == 3
        assert [row["category"] for row in findings] == ["contrast"] * 3

        # Sem política de escrita, o update não alcança linha nenhuma.
        assert db.execute("update analyses set quality_score = 100").rowcount == 0

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(
                "select * from quality_summary(%s, now() - interval '30 days', now())",
                (clinic_b,)
            )
    finally:
        db.execute("reset role")


def test_anonymous_role_sees_no_analyses_and_cannot_aggregate(seed, db):
    clinic = seed.clinic()
    seed.analysis(clinic, 90, findings={"contrast": "attention"})

    as_user(db, "anon")
    try:
        assert db.execute("select * from analyses").fetchall() == []
        assert db.execute("select * from analysis_findings").fetchall() == []

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(
                "select * from quality_summary(%s, now() - interval '30 days', now())",
                (clinic,)
            )
    finally:
        db.execute("reset role")


def test_service_role_can_call_the_aggregations(seed, db):
    clinic = seed.clinic()
    for _ in range(5):
        seed.analysis(clinic, 90)

    as_user(db, "service_role")
    try:
        row = db.execute(
            "select * from quality_summary(%s, now() - interval '400 days', now() + interval '400 days')",
            (clinic,)
        ).fetchone()
    finally:
        db.execute("reset role")

    assert row["total"] == 5


# --- profissional da radiografia e gravação da análise --------------------------

def test_radiograph_rejects_professional_from_another_clinic(seed):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    professional_b = seed.profile(clinic_b)

    with pytest.raises(psycopg.errors.CheckViolation):
        seed.radiograph(clinic_a, professional_b)


def record_analysis(db, radiograph_id, clinic_id, score, is_adequate, findings):
    result = {"efficientnet": {"score": score, "is_adequate": is_adequate, "criteria": findings}}
    row = db.execute(
        """
        select record_analysis(
          p_radiograph_id => %s, p_clinic_id => %s, p_status => %s, p_quality_score => %s::numeric,
          p_is_adequate => %s, p_model_version => 'modelo-de-teste',
          p_recommendation => 'Recomendação de teste.', p_result => %s, p_findings => %s
        ) as id
        """,
        (
            radiograph_id, clinic_id, "approved" if is_adequate else "rejected", score,
            is_adequate, Jsonb(result), Jsonb(findings)
        )
    ).fetchone()
    return str(row["id"])


def test_record_analysis_copies_professional_and_keeps_only_latest_as_current(seed, db):
    clinic = seed.clinic()
    ana = seed.profile(clinic, "Ana")
    radiograph = seed.radiograph(clinic, ana)
    criteria = [
        {"category": "sharpness", "score": 40, "status": "rejected"},
        {"category": "contrast", "score": 80, "status": "approved"},
    ]

    first = record_analysis(db, radiograph, clinic, 42.5, False, criteria)
    second = record_analysis(db, radiograph, clinic, 81.0, True, [])

    rows = db.execute(
        "select id, professional_id, clinic_id, status, quality_score, is_current, "
        "model_version, recommendation, is_adequate from analyses"
    ).fetchall()
    by_id = {str(row["id"]): row for row in rows}

    assert len(rows) == 2
    assert by_id[first]["is_current"] is False
    assert by_id[second]["is_current"] is True
    assert str(by_id[second]["professional_id"]) == ana
    assert float(by_id[first]["quality_score"]) == 42.5
    assert by_id[first]["is_adequate"] is False
    assert by_id[second]["model_version"] == "modelo-de-teste"
    assert by_id[second]["recommendation"] == "Recomendação de teste."

    findings = db.execute(
        "select category, status, score from analysis_findings where analysis_id = %s order by category",
        (first,)
    ).fetchall()
    assert [(f["category"], f["status"], float(f["score"])) for f in findings] == [
        ("contrast", "approved", 80.0), ("sharpness", "rejected", 40.0)
    ]

    stored = db.execute("select analysis_result from radiographs where id = %s", (radiograph,)).fetchone()
    assert stored["analysis_result"]["efficientnet"]["score"] == 81.0


def test_reanalysis_counts_once_in_the_statistics(seed, db):
    clinic = seed.clinic()
    for _ in range(5):
        radiograph = seed.radiograph(clinic)
        record_analysis(db, radiograph, clinic, 20, False, [])
        record_analysis(db, radiograph, clinic, 80, True, [])

    filters = quality_stats.resolve_filters("7", None, None, None, None)
    current = quality_stats.get_summary(clinic, filters).current

    assert current.total == 5
    assert current.avg_score == 80.0
    assert current.status_rates.approved == 100.0


def test_record_analysis_refuses_radiograph_from_another_clinic(seed, db):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    radiograph_b = seed.radiograph(clinic_b)

    with pytest.raises(psycopg.errors.NoDataFound):
        record_analysis(db, radiograph_b, clinic_a, 90, True, [])

    assert db.execute("select count(*) as n from analyses").fetchone()["n"] == 0


# --- dados antigos --------------------------------------------------------------

def test_migration_backfills_old_results_without_the_placeholder_findings(seed, db):
    clinic = seed.clinic()
    legacy = {
        "yolo": {
            "model": "yolov8-dental-14c",
            "findings": [{"class_code": "CAR", "label": "Cárie", "confidence": 0.8}]
        },
        "efficientnet": {
            "model": "efficientnet-b0-baseline",
            "is_adequate": False,
            "score": 37.5,
            "criteria": [
                {"category": "sharpness", "label": "Nitidez", "score": 30, "status": "rejected", "raw_value": 250.0},
                {"category": "coverage", "label": "Cobertura anatômica", "score": None, "status": "pending", "raw_value": None},
            ],
            "recommendation": "..."
        }
    }
    uploaded_at = local_noon(TODAY - timedelta(days=40))
    analyzed = seed.radiograph(clinic, analysis_result=legacy, created_at=uploaded_at)
    seed.radiograph(clinic)

    apply_migrations(db)
    apply_migrations(db)

    rows = db.execute("select * from analyses").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert str(row["radiograph_id"]) == analyzed
    assert row["status"] == "rejected"
    assert float(row["quality_score"]) == 37.5
    assert row["model_version"] == "efficientnet-b0-baseline"
    assert row["recommendation"] == "..."
    assert row["is_adequate"] is False
    assert row["is_current"] is True
    assert row["professional_id"] is None
    assert row["created_at"] == uploaded_at
    assert "yolo" not in row["result"]

    # O critério "pending" não foi avaliado, então não vira achado.
    findings = db.execute("select category, status from analysis_findings order by category").fetchall()
    assert [(f["category"], f["status"]) for f in findings] == [("sharpness", "rejected")]
