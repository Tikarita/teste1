from fastapi import APIRouter

from app.services.supabase_service import supabase


router = APIRouter(
    prefix="/system",
    tags=["System"]
)


@router.get("/database-test")
def database_test():
    """Confere a conexão com o banco. Rota pública, então não devolve dado nenhum."""

    (
        supabase
        .table("clinics")
        .select("id")
        .limit(1)
        .execute()
    )

    return {
        "message": "Conexão com Supabase funcionando"
    }
