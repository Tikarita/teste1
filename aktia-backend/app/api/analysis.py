from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.auth import get_current_user
from app.core.config import settings
from app.schemas.reviews import Review, ReviewCreate
from app.services import finding_validation_service, notification_service, review_service
from app.services.finding_validation_service import FindingValidation, FindingValidationRequest
from app.services.image_service import validate_image
from app.services.supabase_service import supabase

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)


def _get_clinic_radiograph(radiograph_id: str, clinic_id: str) -> dict:
    """Busca a radiografia só dentro da clínica do usuário: a de outra clínica responde 404."""
    response = (
        supabase
        .table("radiographs")
        .select("*")
        .eq("id", radiograph_id)
        .eq("clinic_id", clinic_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Radiografia não encontrada"
        )

    return response.data[0]


def _resolve_professional_id(professional_id: UUID | None, current: dict) -> str:
    """
    Profissional responsável pela captura. Sem valor informado, é o próprio
    usuário logado; quando informado, precisa ser da mesma clínica.
    """
    if professional_id is None or str(professional_id) == str(current["profile"]["id"]):
        return str(current["profile"]["id"])

    response = (
        supabase
        .table("profiles")
        .select("id")
        .eq("id", str(professional_id))
        .eq("clinic_id", current["clinic"]["id"])
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="O profissional informado não pertence a esta clínica."
        )

    return str(professional_id)


@router.post("/upload")
async def upload_radiograph(
    professional_id: UUID | None = Form(None),
    file: UploadFile = File(...),
    current=Depends(get_current_user)
):
    clinic_id = current["clinic"]["id"]
    uploaded_by = current["profile"]["id"]
    professional_id = _resolve_professional_id(professional_id, current)

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
            "professional_id": professional_id,
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
def get_clinic_radiographs(clinic_id: str, current=Depends(get_current_user)):
    if clinic_id != str(current["clinic"]["id"]):
        raise HTTPException(
            status_code=403,
            detail="Você não tem acesso às radiografias desta clínica."
        )

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
def get_radiograph(radiograph_id: str, current=Depends(get_current_user)):
    try:
        radiograph = _get_clinic_radiograph(radiograph_id, current["clinic"]["id"])

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
            "signed_url": signed_url_response,
            "review": review_service.get_current_review(radiograph_id, current["clinic"]["id"]),
            "finding_validations": finding_validation_service.get_current(
                radiograph_id, current["clinic"]["id"]
            )
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/{radiograph_id}/analyze")
def analyze_radiograph_by_id(radiograph_id: str, current=Depends(get_current_user)):
    if not settings.ENABLE_AI:
        raise HTTPException(
            status_code=503,
            detail="A análise por IA ainda não está disponível."
        )

    # Import tardio: o serviço carrega torch, que não é instalado quando a IA está desligada.
    from app.services.analysis_service import analyze_radiograph

    try:
        radiograph = _get_clinic_radiograph(radiograph_id, current["clinic"]["id"])

        image_bytes = supabase.storage.from_("radiographs").download(
            radiograph["file_path"]
        )

        result = analyze_radiograph(image_bytes)
        quality = result["efficientnet"]

        # O modelo atual só decide adequado/inadequado, então o status geral
        # não tem "attention" por enquanto.
        try:
            supabase.rpc("record_analysis", {
                "p_radiograph_id": radiograph_id,
                "p_clinic_id": current["clinic"]["id"],
                "p_status": "approved" if quality["is_adequate"] else "rejected",
                "p_quality_score": quality["score"],
                "p_is_adequate": quality["is_adequate"],
                "p_model_version": quality["model"],
                "p_recommendation": quality["recommendation"],
                "p_result": result,
                # Critérios "pending" não foram avaliados, então não viram achado.
                "p_findings": [
                    {
                        "category": criterion["category"],
                        "status": criterion["status"],
                        "score": criterion["score"]
                    }
                    for criterion in quality["criteria"]
                    if criterion["status"] != "pending"
                ]
            }).execute()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"A análise foi concluída, mas não pôde ser salva: {e}"
            )

        # Aviso em tempo real: aparece na tela de quem está com o paciente.
        if not quality["is_adequate"]:
            try:
                notification_service.notify_inadequate_exam(radiograph, quality, current)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"A análise foi salva, mas o aviso de exame inadequado não pôde ser gerado: {e}"
                )

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


@router.post("/{radiograph_id}/review", response_model=Review, status_code=201)
def review_radiograph(
    radiograph_id: str,
    payload: ReviewCreate,
    current=Depends(get_current_user)
):
    """
    Registra a decisão do profissional sobre o exame (adequado/inadequado,
    motivos e se foi repetido). Revisar de novo não apaga a revisão anterior:
    ela fica no histórico e a nova passa a valer.
    """
    _get_clinic_radiograph(radiograph_id, current["clinic"]["id"])

    return review_service.create_review(radiograph_id, payload, current)


@router.post("/{radiograph_id}/findings/validate", response_model=list[FindingValidation])
def validate_findings(
    radiograph_id: str,
    payload: FindingValidationRequest,
    current=Depends(get_current_user)
):
    """
    Registra a decisão do profissional sobre achados do pré-laudo: confirmado,
    descartado ou "pending" para desfazer. Devolve as decisões vigentes.
    """
    _get_clinic_radiograph(radiograph_id, current["clinic"]["id"])

    return finding_validation_service.save(radiograph_id, payload, current)


@router.delete("/{radiograph_id}")
def delete_radiograph(radiograph_id: str, current=Depends(get_current_user)):
    try:
        radiograph = _get_clinic_radiograph(radiograph_id, current["clinic"]["id"])

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
