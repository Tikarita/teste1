import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


class Settings:
    APP_NAME: str = "AktIA API"
    VERSION: str = "1.0.0"

    # Em produção, defina CORS_ORIGINS com o domínio do frontend
    # (ex.: "https://aktia.vercel.app"), separando vários por vírgula.
    CORS_ORIGINS: list[str] = _env_list("CORS_ORIGINS", [
        "http://localhost:5173",
        "http://localhost:3000"
    ])

    # ENABLE_AI=false sobe a API sem torch/torchvision (deploy sem a IA).
    ENABLE_AI: bool = os.getenv("ENABLE_AI", "true").lower() not in ("false", "0", "no")

    ALLOWED_IMAGE_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/jpg"
    ]

    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024


settings = Settings()
