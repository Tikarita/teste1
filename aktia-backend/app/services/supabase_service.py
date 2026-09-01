import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        f"SUPABASE_URL ou SUPABASE_KEY não foram configurados. "
        f"Arquivo esperado em: {BASE_DIR / '.env'}"
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)