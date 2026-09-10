from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.clinics import router as clinics_router
from app.api.staff import router as staff_router
from app.api.system import router as system_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(clinics_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "AktIA API online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }