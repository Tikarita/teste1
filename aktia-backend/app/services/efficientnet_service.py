import json
from io import BytesIO
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

# Referência de "normalidade" pré-calculada offline (ver
# baseline_efficientnet.py na raiz do repo) a partir de ~500 radiografias
# de dados/images/train. Bundlada aqui para o backend não depender da pasta
# de treino em produção.
REFERENCE_PATH = Path(__file__).resolve().parent.parent / "ml" / "efficientnet_reference.json"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMG_SIZE = 512

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

_model: nn.Module | None = None
_reference: dict | None = None


def _get_model() -> nn.Module:
    global _model
    if _model is None:
        model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
        model.classifier = nn.Identity()
        model.eval()
        _model = model.to(DEVICE)
    return _model


def _get_reference() -> dict:
    global _reference
    if _reference is None:
        if not REFERENCE_PATH.exists():
            raise FileNotFoundError(
                f"Referência do EfficientNet não encontrada em {REFERENCE_PATH}. "
                "Gere com baseline_efficientnet.py (ver raiz do repositório)."
            )
        with open(REFERENCE_PATH, "r", encoding="utf-8") as f:
            _reference = json.load(f)
    return _reference


def _embed(image_bytes: bytes) -> np.ndarray:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = _TRANSFORM(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        embedding = _get_model()(tensor)[0].cpu().numpy()

    norm = np.linalg.norm(embedding)
    return embedding / norm if norm > 1e-8 else embedding


def classify_adequacy(image_bytes: bytes) -> dict:
    """
    Classifica a radiografia como adequada/inadequada usando a EfficientNet-B0
    como extrator de features + distância a um centróide de "normalidade"
    (ver baseline_efficientnet.py). Ainda não é um classificador supervisionado
    — não há rótulos aceitável/inaceitável reais para treinar um ainda —, mas
    já é uma inferência de rede neural de verdade, não um placeholder.

    Quando existir dataset rotulado, troque esta função para carregar o
    checkpoint supervisionado treinado por train_efficientnet.py (mesma
    arquitetura, cabeça de classificação em vez de distância a um centróide).
    """
    reference = _get_reference()
    centroid = np.array(reference["centroid"])
    threshold = reference["threshold"]

    embedding = _embed(image_bytes)
    distance = float(np.linalg.norm(embedding - centroid))
    is_adequate = distance <= threshold
    score = round(max(0.0, min(100.0, 100 * (1 - distance / (2 * threshold)))), 1)

    return {
        "model": "efficientnet-b0-baseline",
        "label": "adequado" if is_adequate else "inadequado",
        "is_adequate": is_adequate,
        "score": score,
        "distance": round(distance, 4),
        "threshold": round(threshold, 4),
    }
