import os
import shutil
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# O app cria o cliente do Supabase ao ser importado. Os testes nunca falam com
# um projeto real: as agregações rodam num Postgres local e o restante usa um
# cliente falso.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test.test.test")
os.environ["STATS_MIN_SAMPLE_SIZE"] = "5"
os.environ["STATS_TIMEZONE"] = "America/Sao_Paulo"

from app.api.auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.services import quality_stats, report_service  # noqa: E402


BACKEND_DIR = Path(__file__).resolve().parents[1]
BOOTSTRAP_SQL = Path(__file__).resolve().parent / "sql" / "bootstrap.sql"
# radiographs.analysis_result (migrations_add_analysis_result.sql) já está no
# banco real, então faz parte do bootstrap e não é reaplicada aqui.
MIGRATIONS = sorted((BACKEND_DIR.parent / "supabase" / "migrations").glob("*.sql"))

TIMEZONE = ZoneInfo("America/Sao_Paulo")

# "Hoje" fixo, para os períodos de 7/30/90 dias não dependerem do relógio.
TODAY = date(2026, 6, 30)


def local_noon(day: date) -> datetime:
    return datetime.combine(day, time(12, 0), tzinfo=TIMEZONE)


def apply_migrations(connection) -> None:
    for migration in MIGRATIONS:
        connection.execute(migration.read_text(encoding="utf-8"))


def _ensure_timezone_data() -> None:
    """
    O Postgres embutido do pgserver para Windows vem sem a base de fusos
    horários, e as agregações por dia precisam dela ("America/Sao_Paulo").
    O pacote tzdata traz os mesmos arquivos, no formato que o Postgres lê.
    """
    import pgserver
    import tzdata

    target = Path(pgserver.__file__).parent / "pginstall" / "share" / "postgresql" / "timezone"
    if not target.exists():
        shutil.copytree(Path(tzdata.__file__).parent / "zoneinfo", target)


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        yield url
        return

    import pgserver

    _ensure_timezone_data()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as data_dir:
        server = pgserver.get_server(data_dir, cleanup_mode="stop")
        try:
            yield server.get_uri()
        finally:
            server.cleanup()


@pytest.fixture(scope="session")
def _schema(database_url):
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(BOOTSTRAP_SQL.read_text(encoding="utf-8"))
        apply_migrations(connection)


@pytest.fixture
def db(database_url, _schema):
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as connection:
        connection.execute(
            "truncate radiograph_reviews, reports, analysis_findings, analyses, radiographs, profiles, clinics, "
            "auth.users, storage.objects cascade"
        )
        yield connection


class Seed:
    """Atalhos para montar os dados de cada teste direto no banco."""

    def __init__(self, connection):
        self.connection = connection

    def clinic(self, name: str = "Clínica") -> str:
        row = self.connection.execute(
            "insert into clinics (name) values (%s) returning id", (name,)
        ).fetchone()
        return str(row["id"])

    def profile(self, clinic_id: str, name: str = "Profissional") -> str:
        user_id = str(uuid4())
        self.connection.execute("insert into auth.users (id) values (%s)", (user_id,))
        self.connection.execute(
            "insert into profiles (id, clinic_id, full_name, role) values (%s, %s, %s, 'user')",
            (user_id, clinic_id, name)
        )
        return user_id

    def radiograph(self, clinic_id: str, professional_id: str | None = None, **extra) -> str:
        columns = {
            "clinic_id": clinic_id, "professional_id": professional_id,
            "file_name": "rx.jpg", "file_path": f"{uuid4()}.jpg", **extra
        }
        names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        row = self.connection.execute(
            f"insert into radiographs ({names}) values ({placeholders}) returning id",
            [Jsonb(v) if isinstance(v, dict) else v for v in columns.values()]
        ).fetchone()
        return str(row["id"])

    def analysis(
        self,
        clinic_id: str,
        score: float,
        status: str = "approved",
        day: date = TODAY,
        professional_id: str | None = None,
        created_at: datetime | None = None,
        findings: dict[str, str] | None = None,
        result: dict | None = None
    ) -> str:
        """Uma radiografia com a sua análise atual. `findings` é {categoria: status}."""
        radiograph_id = self.radiograph(clinic_id, professional_id)
        row = self.connection.execute(
            """
            insert into analyses (
              radiograph_id, clinic_id, professional_id, status,
              quality_score, is_adequate, model_version, created_at, result
            )
            values (%s, %s, %s, %s, %s, %s, 'modelo-de-teste', %s, %s)
            returning id
            """,
            (
                radiograph_id, clinic_id, professional_id, status,
                score, status == "approved", created_at or local_noon(day),
                Jsonb(result) if result is not None else None
            )
        ).fetchone()

        for category, finding_status in (findings or {}).items():
            self.connection.execute(
                """
                insert into analysis_findings (analysis_id, category, status, score)
                values (%s, %s, %s, 50)
                """,
                (row["id"], category, finding_status)
            )

        return str(row["id"])


@pytest.fixture
def seed(db):
    return Seed(db)


@pytest.fixture
def rpc_on_database(db, monkeypatch):
    """Faz o serviço de estatísticas chamar as funções SQL de verdade, no Postgres de teste."""

    def run(function_name: str, params: dict) -> list[dict]:
        arguments = ", ".join(f"{name} => %({name})s" for name in params)
        return db.execute(f"select * from {function_name}({arguments})", params).fetchall()

    def staff(clinic_id: str) -> list[dict]:
        return db.execute(
            "select id, full_name from profiles where clinic_id = %s", (clinic_id,)
        ).fetchall()

    monkeypatch.setattr(quality_stats, "_rpc", run)
    monkeypatch.setattr(quality_stats, "_clinic_staff", staff)


@pytest.fixture
def reports_on_database(db, rpc_on_database, monkeypatch):
    """Grava e lê relatórios na tabela `reports` do Postgres de teste."""

    def insert(row: dict) -> dict:
        columns = ", ".join(row)
        placeholders = ", ".join(["%s"] * len(row))
        return db.execute(
            f"insert into reports ({columns}) values ({placeholders}) returning *",
            [Jsonb(value) if isinstance(value, (dict, list)) else value for value in row.values()]
        ).fetchone()

    def select(clinic_id: str, report_id: str | None = None) -> list[dict]:
        return db.execute(
            """
            select * from reports
            where clinic_id = %s and report_type = 'quality'
              and (%s::uuid is null or id = %s::uuid)
            order by created_at desc
            """,
            (clinic_id, report_id, report_id)
        ).fetchall()

    monkeypatch.setattr(report_service, "_insert_report", insert)
    monkeypatch.setattr(report_service, "_select_reports", select)


def session_for(clinic_id: str, profile_id: str, role: str = "user") -> dict:
    """O que get_current_user devolve para um usuário logado."""
    return {
        "profile": {"id": profile_id, "clinic_id": clinic_id, "role": role, "full_name": "Usuária de Teste"},
        "clinic": {"id": clinic_id, "name": "Clínica", "cnpj": "00.000.000/0001-91"}
    }


@pytest.fixture
def login():
    """Autentica as próximas requisições como o usuário informado."""

    def _login(clinic_id: str, profile_id: str, role: str = "user") -> None:
        app.dependency_overrides[get_current_user] = lambda: session_for(clinic_id, profile_id, role)

    yield _login
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)
