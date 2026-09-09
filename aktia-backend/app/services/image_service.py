from io import BytesIO

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError


def validate_image(file_content: bytes, max_size_bytes: int) -> None:
    if len(file_content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Arquivo vazio."
        )

    if len(file_content) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo muito grande. Tamanho máximo: {max_size_bytes // (1024 * 1024)}MB."
        )

    try:
        image = Image.open(BytesIO(file_content))
        image.verify()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Arquivo não é uma imagem válida."
        )
