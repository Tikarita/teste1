from io import BytesIO
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

from app.services.model_store import ensure_model_file

# YOLOv8m treinado nas 14 classes de achados de dados/data.yaml. O .pt fica
# fora do Git (*.pt no .gitignore): precisa ser copiado para app/ml/ em cada
# ambiente.
WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "ml" / "yolo_14classes_1024_best.pt"

MODEL_NAME = "yolov8m-dental-14c-1024-v1"

# Mesmo tamanho de entrada do treino.
IMG_SIZE = 1024

# Limiar de confiança padrão do Ultralytics para predição. Não foi ajustado
# para este modelo: subir reduz falsos achados, descer reduz achados perdidos.
CONFIDENCE_THRESHOLD = 0.25

_model: YOLO | None = None


def _get_model() -> YOLO:
    global _model
    if _model is None:
        ensure_model_file(WEIGHTS_PATH)
        _model = YOLO(str(WEIGHTS_PATH))
    return _model


def detect_findings(image_bytes: bytes) -> list[dict]:
    """
    Detecta achados na radiografia. Cada item traz o código da classe, a
    confiança da detecção e a caixa em frações (0-1) da largura e da altura
    da imagem, com `x`/`y` no canto superior esquerdo.

    No conjunto de teste o modelo teve mAP50 de 0,537: ele erra e deixa passar
    achados com frequência, então o resultado é apoio à leitura, não laudo.
    """
    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    result = _get_model().predict(
        image,
        imgsz=IMG_SIZE,
        conf=CONFIDENCE_THRESHOLD,
        verbose=False
    )[0]

    findings = []
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxyn[0].tolist()
        findings.append({
            "class_code": result.names[int(box.cls[0])],
            "confidence": round(float(box.conf[0]), 4),
            "bbox": {
                "x": round(x1, 4),
                "y": round(y1, 4),
                "width": round(x2 - x1, 4),
                "height": round(y2 - y1, 4)
            }
        })

    findings.sort(key=lambda finding: finding["confidence"], reverse=True)
    return findings
