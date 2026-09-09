from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.services.analysis_service import analyze_radiograph
from app.services.image_service import validate_image
from app.services.supabase_service import supabase

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)


@router.post("/upload")
async def upload_radiograph(
    clinic_id: str = Form(...),
    uploaded_by: str = Form(...),
    file: UploadFile = File(...)
):
    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não suportado. Envie JPG ou PNG."
        )

    file_content = await file.read()

    validate_image(file_content, max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES)

    file_extension = file.filename.split(".")[-1]
    unique_file_name = f"{uuid4()}.{file_extension}"

    try:
        supabase.storage.from_("radiographs").upload(
            path=unique_file_name,
            file=file_content,
            file_options={
                "content-type": file.content_type
            }
        )

        radiograph_data = {
            "clinic_id": clinic_id,
            "uploaded_by": uploaded_by,
            "file_name": file.filename,
            "file_path": unique_file_name,
            "file_type": file.content_type,
            "file_size": len(file_content)
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

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/clinic/{clinic_id}")
def get_clinic_radiographs(clinic_id: str):
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


@router.get("/{radiograph_id}")
def get_radiograph(radiograph_id: str):
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


@router.post("/{radiograph_id}/analyze")
def analyze_radiograph_by_id(radiograph_id: str):
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

        image_bytes = supabase.storage.from_("radiographs").download(
            radiograph["file_path"]
        )

        result = analyze_radiograph(image_bytes)

        try:
            supabase.table("radiographs").update({
                "analysis_result": result
            }).eq("id", radiograph_id).execute()
        except Exception:
            pass

        return {
            "data": result
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete("/{radiograph_id}")
def delete_radiograph(radiograph_id: str):
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

        supabase.storage.from_("radiographs").remove([
            radiograph["file_path"]
        ])

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
