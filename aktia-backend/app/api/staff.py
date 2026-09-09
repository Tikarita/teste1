import secrets
import string

from fastapi import APIRouter, HTTPException

from app.schemas.staff import StaffCreate
from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/staff",
    tags=["Staff"]
)


def _generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14)) + "Ax1!"


@router.post("/")
def create_staff(staff: StaffCreate):
    """
    Cria uma conta real no Supabase Auth para o funcionário e o vincula à
    clínica em `profiles`. É necessário porque `radiographs.uploaded_by`
    tem uma foreign key para `profiles`, que por sua vez exige um usuário
    existente em `auth.users` — não basta um registro solto numa tabela.
    """

    temporary_password = _generate_temporary_password()

    try:
        auth_response = supabase.auth.admin.create_user({
            "email": staff.email,
            "password": temporary_password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": staff.full_name,
                "clinic_id": str(staff.clinic_id),
                "role": staff.role
            }
        })
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    user_id = auth_response.user.id

    try:
        supabase.table("profiles").upsert({
            "id": user_id,
            "clinic_id": str(staff.clinic_id),
            "full_name": staff.full_name,
            "email": staff.email,
            "role": staff.role
        }).execute()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    return {
        "message": "Funcionário cadastrado com sucesso",
        "data": {
            "id": user_id,
            "clinic_id": str(staff.clinic_id),
            "full_name": staff.full_name,
            "email": staff.email,
            "role": staff.role
        },
        "temporary_password": temporary_password
    }


@router.get("/clinic/{clinic_id}")
def list_staff_by_clinic(clinic_id: str):
    try:
        response = (
            supabase
            .table("profiles")
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
