from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.schemas.clinic import ClinicCreate
from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/clinics",
    tags=["Clinics"]
)


@router.post("/")
def create_clinic(clinic: ClinicCreate, current=Depends(get_current_user)):

    try:
        response = (
            supabase
            .table("clinics")
            .insert({
                "name": clinic.name,
                "cnpj": clinic.cnpj
            })
            .execute()
        )

        return {
            "message": "Clínica cadastrada com sucesso",
            "data": response.data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@router.get("/")
def list_clinics(current=Depends(get_current_user)):
    """Só a clínica do usuário logado: a lista completa exporia todas as clínicas da base."""
    return {
        "data": [current["clinic"]]
    }
