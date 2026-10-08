from datetime import datetime
from io import BytesIO

import numpy as np
import pydicom
from fastapi import HTTPException
from PIL import Image
from pydicom.errors import InvalidDicomError
from pydicom.pixels import apply_modality_lut, apply_voi_lut

DICOM_CONTENT_TYPES = {"application/dicom", "application/dicom+json", "application/x-dicom"}

# Só dados técnicos do exame. Nome, identificador, data de nascimento, sexo,
# endereço e qualquer outro dado do paciente ficam de fora de propósito: o
# arquivo DICOM original não é armazenado, só a imagem convertida e estes campos.
_TECHNICAL_FIELDS = {
    "modality": "Modality",
    "manufacturer": "Manufacturer",
    "model": "ManufacturerModelName",
    "station_name": "StationName",
    "software_version": "SoftwareVersions",
    "body_part": "BodyPartExamined",
    "kvp": "KVP",
    "tube_current_ma": "XRayTubeCurrent",
    "exposure_time_ms": "ExposureTime",
    "exposure_mas": "Exposure",
    "dose_area_product": "ImageAndFluoroscopyAreaDoseProduct",
}


def is_dicom(file_content: bytes, content_type: str | None, file_name: str | None) -> bool:
    """Arquivos DICOM têm a marca "DICM" depois de um cabeçalho de 128 bytes."""
    if file_content[128:132] == b"DICM":
        return True

    by_name = (file_name or "").lower().endswith((".dcm", ".dicom"))
    return by_name or (content_type or "").lower() in DICOM_CONTENT_TYPES


def _plain(value):
    """Valor do DICOM como texto ou número simples, para guardar em JSON."""
    if value is None or value == "":
        return None
    if isinstance(value, (list, tuple, pydicom.multival.MultiValue)):
        return ", ".join(str(item) for item in value) or None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return str(value).strip() or None


def _exam_date(dataset) -> str | None:
    for field in ("AcquisitionDate", "ContentDate", "StudyDate"):
        raw = str(getattr(dataset, field, "") or "")
        try:
            return datetime.strptime(raw[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            continue
    return None


def _to_8bit(dataset) -> np.ndarray:
    """
    Aplica as transformações que o próprio arquivo define (escala da
    modalidade e janela de visualização) e converte para tons de cinza de
    8 bits, como um visualizador faria.
    """
    pixels = dataset.pixel_array

    if pixels.ndim != 2:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este arquivo DICOM não é uma radiografia 2D em tons de cinza (pode ser uma tomografia "
                "ou uma imagem colorida). Envie uma radiografia panorâmica."
            )
        )

    values = apply_modality_lut(pixels, dataset)
    has_window = "WindowCenter" in dataset or "VOILUTSequence" in dataset
    values = np.asarray(apply_voi_lut(values, dataset) if has_window else values, dtype=np.float64)

    if has_window:
        low, high = float(values.min()), float(values.max())
    else:
        # Sem janela definida no arquivo: descarta 0,5% de cada extremo para
        # um pixel isolado muito claro ou escuro não achatar o contraste.
        low, high = np.percentile(values, [0.5, 99.5])

    if high <= low:
        scaled = np.zeros(values.shape, dtype=np.uint8)
    else:
        scaled = (np.clip((values - low) / (high - low), 0, 1) * 255).round().astype(np.uint8)

    # MONOCHROME1: o valor mais alto é o mais escuro. Inverte para o padrão
    # das demais imagens (osso e metal claros).
    if str(getattr(dataset, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        scaled = 255 - scaled

    return scaled


def convert(file_content: bytes) -> tuple[bytes, dict]:
    """
    Converte um DICOM de radiografia em PNG e devolve, junto, os dados
    técnicos do exame. Nenhum dado do paciente sai daqui.
    """
    try:
        dataset = pydicom.dcmread(BytesIO(file_content))
    except (InvalidDicomError, Exception):
        raise HTTPException(
            status_code=400,
            detail="O arquivo não é um DICOM válido."
        )

    if "PixelData" not in dataset:
        raise HTTPException(
            status_code=400,
            detail="Este arquivo DICOM não contém imagem."
        )

    if int(getattr(dataset, "NumberOfFrames", 1) or 1) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este arquivo DICOM tem várias imagens (por exemplo, uma tomografia). "
                "Envie uma radiografia de imagem única."
            )
        )

    try:
        pixels = _to_8bit(dataset)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível ler a imagem deste DICOM, provavelmente por usar um tipo de compressão "
                f"sem suporte ({dataset.file_meta.TransferSyntaxUID.name}). Exporte sem compressão ou em JPG/PNG. "
                f"Detalhe: {error}"
            )
        )

    buffer = BytesIO()
    Image.fromarray(pixels, mode="L").save(buffer, format="PNG")

    metadata = {"source_format": "dicom", "exam_date": _exam_date(dataset)}
    for key, field in _TECHNICAL_FIELDS.items():
        metadata[key] = _plain(getattr(dataset, field, None))

    metadata["width"] = int(dataset.Columns)
    metadata["height"] = int(dataset.Rows)
    metadata["bits_stored"] = _plain(getattr(dataset, "BitsStored", None))
    # Alguns aparelhos gravam o nome do paciente dentro da própria imagem. O
    # arquivo avisa quando faz isso; a tela mostra o alerta.
    metadata["burned_in_annotation"] = str(getattr(dataset, "BurnedInAnnotation", "")).upper() == "YES"

    return buffer.getvalue(), {key: value for key, value in metadata.items() if value is not None}
