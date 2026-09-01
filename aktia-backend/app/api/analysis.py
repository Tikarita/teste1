from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.supabase_service import supabase
from uuid import uuid4

router = APIRouter(
prefix="/api/v1/analysis",
tags=["Analysis"]
)

@router.post("/upload")
async def upload_radiograph(
clinic_id: str = Form(...),
uploaded_by: str = Form(...),
file: UploadFile = File(...)
):
allowed_types = [
"image/jpeg",
"image/png",
"image/jpg"
]

```
if file.content_type not in allowed_types:
    raise HTTPException(
        status_code=400,
        detail="Formato de arquivo não suportado. Envie JPG ou PNG."
    )

file_extension = file.filename.split(".")[-1]

unique_file_name = f"{uuid4()}.{file_extension}"

file_content = await file.read()

file_size = len(file_content)

try:

    # Envia a imagem para o Supabase Storage
    supabase.storage.from_(
        "radiographs"
    ).upload(
        path=unique_file_name,
        file=file_content,
        file_options={
            "content-type": file.content_type
        }
    )

    # Registra a radiografia no banco
    radiograph_data = {
        "clinic_id": clinic_id,
        "uploaded_by": uploaded_by,
        "file_name": file.filename,
        "file_path": unique_file_name,
        "file_type": file.content_type,
        "file_size": file_size
    }

    response = (
        supabase
        .table("radiographs")
        .insert(radiograph_data)
        .execute()
    )

    return {
        "message": "Radiografia enviada e registrada com sucesso",
        "data": response.data
    }

except Exception as e:

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )
```

@router.get("/clinic/{clinic_id}")
def get_clinic_radiographs(clinic_id: str):

```
try:

    response = (
        supabase
        .table("radiographs")
        .select("*")
        .eq("clinic_id", clinic_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "data": response.data
    }

except Exception as e:

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )
```

@router.get("/{radiograph_id}")
def get_radiograph(radiograph_id: str):

```
try:

    response = (
        supabase
        .table("radiographs")
        .select("*")
        .eq("id", radiograph_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Radiografia não encontrada"
        )

    radiograph = response.data[0]

    signed_url_response = (
        supabase
        .storage
        .from_("radiographs")
        .create_signed_url(
            radiograph["file_path"],
            3600
        )
    )

    return {
        "data": radiograph,
        "signed_url": signed_url_response
    }

except HTTPException:
    raise

except Exception as e:

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )
```

@router.delete("/{radiograph_id}")
def delete_radiograph(radiograph_id: str):

```
try:

    # Busca a radiografia no banco
    response = (
        supabase
        .table("radiographs")
        .select("*")
        .eq("id", radiograph_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Radiografia não encontrada"
        )

    radiograph = response.data[0]

    # Remove o arquivo do Storage
    supabase.storage.from_(
        "radiographs"
    ).remove([
        radiograph["file_path"]
    ])

    # Remove o registro do banco
    (
        supabase
        .table("radiographs")
        .delete()
        .eq("id", radiograph_id)
        .execute()
    )

    return {
        "message": "Radiografia excluída com sucesso",
        "id": radiograph_id
    }

except HTTPException:
    raise

except Exception as e:

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )
```
