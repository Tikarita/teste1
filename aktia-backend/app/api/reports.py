from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.schemas.reports import QualityReport, QualityReportCreate, ReportSummary
from app.services import pre_report_service, report_service
from app.services.pre_report_service import PreReport, PreReportCreate, PreReportSummary


router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


# A clínica vem sempre do usuário autenticado. Não há rota de edição nem de
# exclusão: relatório emitido é registro, e fica como foi emitido.

@router.post("/quality", response_model=QualityReport, status_code=201)
def create_quality_report(payload: QualityReportCreate, current=Depends(get_current_user)):
    return report_service.create_quality_report(
        current,
        payload.period_start,
        payload.period_end,
        payload.notes
    )


@router.get("/quality", response_model=list[ReportSummary])
def list_quality_reports(current=Depends(get_current_user)):
    return report_service.list_quality_reports(current["clinic"]["id"])


@router.get("/quality/{report_id}", response_model=QualityReport)
def get_quality_report(report_id: UUID, current=Depends(get_current_user)):
    return report_service.get_quality_report(current["clinic"]["id"], str(report_id))


# --- Pré-laudo -------------------------------------------------------------------

@router.post("/pre", response_model=PreReport, status_code=201)
def create_pre_report(payload: PreReportCreate, current=Depends(get_current_user)):
    return pre_report_service.create(payload, current)


@router.get("/pre", response_model=list[PreReportSummary])
def list_pre_reports(radiograph_id: UUID, current=Depends(get_current_user)):
    return pre_report_service.list_for_radiograph(current["clinic"]["id"], radiograph_id)


@router.get("/pre/{report_id}", response_model=PreReport)
def get_pre_report(report_id: UUID, current=Depends(get_current_user)):
    return pre_report_service.get(current["clinic"]["id"], report_id)
