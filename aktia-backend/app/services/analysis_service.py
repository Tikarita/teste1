from io import BytesIO

import numpy as np
from PIL import Image

from app.services import yolo_service
from app.services.efficientnet_service import classify_adequacy
from app.services.finding_labels import CLASS_LABELS, LOW_RELIABILITY_CLASSES

# Medidas clássicas de visão computacional calculadas direto da imagem.
#
# Até out/2026 elas viravam "critérios" com nota e status (aprovado/atenção/
# reprovado). Validadas contra os 5.012 rótulos adequado/inadequado de
# dados/labels_qualidade.csv, não se sustentaram: dentro de cada base de
# imagens a AUC de cada uma fica entre 0,45 e 0,49 na direção assumida (0,50 é
# acaso), e no split de teste as imagens "reprovadas" em nitidez tinham 33% de
# inadequadas contra 35% no geral. Juntas numa regressão logística chegam a
# AUC 0,59 no teste, quase toda vinda de diferenças entre as bases, não de
# qualidade. Por isso deixaram de ter nota e status e de alimentar
# estatísticas e relatórios: ficam só como medida técnica informativa.
#
# Posicionamento e cobertura anatômica nunca foram calculados. O caminho para
# ter critérios de verdade são os motivos de rejeição que a revisão humana
# passa a registrar (ver review_service), que servem de rótulo por critério.
IMAGE_MEASUREMENTS = [
    ("sharpness", "Nitidez (variância do Laplaciano)"),
    ("contrast", "Contraste (desvio padrão da intensidade)"),
    ("saturation", "Pixels saturados (fração)")
]

MAX_DIMENSION = 768


def run_yolo_detection(image_bytes: bytes) -> dict:
    """
    Detecção de achados clínicos para o pré-laudo (YOLOv8m, 14 classes de
    dados/data.yaml — ver yolo_service.detect_findings).

    `available: True` indica que os achados vieram do modelo treinado. Com
    isso, uma lista vazia passa a significar "nada detectado".
    """
    findings = [
        {
            "class_code": finding["class_code"],
            "label": CLASS_LABELS.get(finding["class_code"], finding["class_code"]),
            "confidence": finding["confidence"],
            "low_reliability": finding["class_code"] in LOW_RELIABILITY_CLASSES,
            "bbox": finding["bbox"]
        }
        for finding in yolo_service.detect_findings(image_bytes)
    ]

    return {
        "model": yolo_service.MODEL_NAME,
        "available": True,
        "findings": findings
    }


def _load_grayscale_array(image_bytes: bytes) -> np.ndarray:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    width, height = image.size
    scale = MAX_DIMENSION / max(width, height)
    if scale < 1:
        image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))))
    return np.asarray(image, dtype=np.float32)


def _sharpness_metric(gray: np.ndarray) -> float:
    """Variância do filtro de Laplace: quanto mais borrada a imagem, menor a variância."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        # Imagem menor que o kernel 3x3 não tem textura suficiente para
        # medir nitidez — sem essa guarda, a fatia [1:-1,1:-1] fica vazia
        # e .var() devolve NaN, que se propaga como score inválido.
        return 0.0

    laplacian = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(laplacian.var())


def _contrast_metric(gray: np.ndarray) -> float:
    """Contraste RMS: desvio padrão da intensidade normalizada (0-1)."""
    return float((gray / 255.0).std())


def _clipping_metric(gray: np.ndarray) -> float:
    """Fração de pixels estourados (muito escuros ou muito claros) — indício de exposição ruim."""
    return float(np.mean((gray <= 3) | (gray >= 252)))


def run_efficientnet_adequacy(image_bytes: bytes) -> dict:
    """
    Controle de qualidade técnica da radiografia (adequado/inadequado).

    A decisão (`is_adequate`/`score`/`confidence`/`model`) e a explicação
    visual vêm da EfficientNet-B0 supervisionada (ver
    efficientnet_service.classify_adequacy). `score` é a probabilidade de
    "adequado" em escala 0-100.

    `image_measurements` são medidas brutas da imagem, só informativas (ver
    IMAGE_MEASUREMENTS). `criteria` fica vazio: não há critério de qualidade
    automático validado.
    """
    gray = _load_grayscale_array(image_bytes)
    values = {
        "sharpness": _sharpness_metric(gray),
        "contrast": _contrast_metric(gray),
        "saturation": _clipping_metric(gray)
    }

    model_result = classify_adequacy(image_bytes)

    recommendation = (
        "O classificador considerou a qualidade técnica adequada."
        if model_result["is_adequate"] else
        "O classificador apontou qualidade técnica abaixo do ideal. Avalie a imagem e registre a revisão."
    )

    return {
        "model": model_result["model"],
        "is_adequate": model_result["is_adequate"],
        "score": model_result["score"],
        "confidence": model_result["confidence"],
        "explanation": model_result["explanation"],
        "criteria": [],
        "image_measurements": [
            {"key": key, "label": label, "value": round(values[key], 4)}
            for key, label in IMAGE_MEASUREMENTS
        ],
        "recommendation": recommendation
    }


def analyze_radiograph(image_bytes: bytes) -> dict:
    return {
        "yolo": run_yolo_detection(image_bytes),
        "efficientnet": run_efficientnet_adequacy(image_bytes)
    }
