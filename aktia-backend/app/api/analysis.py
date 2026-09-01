from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.analysis_service import analyze_radiograph


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)


@router.post("/")
async def analyze(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Nenhum arquivo enviado"
        )

    allowed_extensions = (
        ".jpg",
        ".jpeg",
        ".png"
    )

    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado"
        )

    image_bytes = await file.read()

    result = analyze_radiograph(image_bytes)

    return result