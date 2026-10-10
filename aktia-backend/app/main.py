from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.clinics import router as clinics_router
from app.api.notifications import router as notifications_router
from app.api.reports import router as reports_router
from app.api.staff import router as staff_router
from app.api.stats import router as stats_router
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
app.include_router(stats_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


def mount_frontend(application: FastAPI, dist: Path) -> None:
    """
    Serve o frontend já compilado (pasta `dist` do Vite) no mesmo endereço da
    API. É o arranjo de produção: um serviço só, sem CORS entre site e API.
    Qualquer caminho que não seja arquivo devolve o index.html, porque as
    rotas das telas (/radiografias, /relatorios...) são resolvidas no navegador.
    """
    dist = dist.resolve()
    index = dist / "index.html"

    application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        requested = (dist / path).resolve()
        # Só arquivos de dentro da pasta do frontend: nada de ../ para fora dela.
        if path and requested.is_file() and requested.is_relative_to(dist):
            return FileResponse(requested)

        return FileResponse(index)


if settings.FRONTEND_DIST and (Path(settings.FRONTEND_DIST) / "index.html").exists():
    mount_frontend(app, Path(settings.FRONTEND_DIST))
else:
    @app.get("/")
    def root():
        return {
            "message": "AktIA API online"
        }
