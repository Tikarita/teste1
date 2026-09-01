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

        # 1. Envia a imagem para o Supabase Storage
        supabase.storage.from_(
            "radiographs"
        ).upload(
            path=unique_file_name,
            file=file_content,
            file_options={
                "content-type": file.content_type
            }
        )

        # 2. Registra a radiografia no banco
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