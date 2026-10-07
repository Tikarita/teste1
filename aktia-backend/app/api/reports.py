from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.schemas.reports import QualityReport, QualityReportCreate, ReportSummary
from app.services import report_service


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
