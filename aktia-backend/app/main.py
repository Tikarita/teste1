from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.clinics import router as clinics_router
from app.api.analysis import router as analysis_router
from app.api.system import router as system_router
from app.api.users import router as users_router

app = FastAPI(
    title="AktIA API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(
    analysis_router,
    prefix="/api/v1"
)


app.include_router(
    system_router,
    prefix="/api/v1"
)


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
app.include_router(
    clinics_router,
    prefix="/api/v1"
)
app.include_router(
    users_router,
    prefix="/api/v1"
)