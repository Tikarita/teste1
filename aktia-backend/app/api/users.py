from fastapi import APIRouter, HTTPException

from app.schemas.user import UserCreate
from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("/")
def create_user(user: UserCreate):

    try:
        response = (
            supabase
            .table("users")
            .insert({
                "clinic_id": str(user.clinic_id),
                "name": user.name,
                "email": user.email,
                "role": user.role
            })
            .execute()
        )

        return {
            "message": "Usuário cadastrado com sucesso",
            "data": response.data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@router.get("/")
def list_users():

    try:
        response = (
            supabase
            .table("users")
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


@router.get("/clinic/{clinic_id}")
def list_users_by_clinic(clinic_id: str):

    try:
        response = (
            supabase
            .table("users")
            .select("*")
            .eq("clinic_id", clinic_id)
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