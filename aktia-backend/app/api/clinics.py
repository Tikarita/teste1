from fastapi import APIRouter, HTTPException

from app.schemas.clinic import ClinicCreate
from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/clinics",
    tags=["Clinics"]
)


@router.post("/")
def create_clinic(clinic: ClinicCreate):

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
def list_clinics():

    try:
        response = (
            supabase
            .table("clinics")
            .select("*")
            .execute()
        )

        return {
            "data": response.data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )