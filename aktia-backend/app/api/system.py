from fastapi import APIRouter

from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/system",
    tags=["System"]
)


@router.get("/database-test")
def database_test():

    response = (
        supabase
        .table("clinics")
        .select("*")
        .limit(1)
        .execute()
    )

    return {
        "message": "Conexão com Supabase funcionando",
        "data": response.data
    }