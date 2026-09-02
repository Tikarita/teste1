from app.services.supabase_service import supabase

try:
    response = (
        supabase
        .table("radiographs")
        .select("*")
        .limit(1)
        .execute()
    )

    print("SUCESSO!")
    print(response.data)

except Exception as e:
    print("ERRO:")
    print(type(e))
    print(str(e))