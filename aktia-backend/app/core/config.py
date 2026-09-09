class Settings:
    APP_NAME: str = "AktIA API"
    VERSION: str = "1.0.0"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000"
    ]

    ALLOWED_IMAGE_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/jpg"
    ]

    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024


settings = Settings()
