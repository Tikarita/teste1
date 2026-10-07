import json
from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import transforms
from torchvision.models import efficientnet_b0

# Classificador supervisionado adequado/inadequado treinado por
# train_efficientnet.py (raiz do repo). O .pt é só o state_dict e fica fora do
# Git (*.pt no .gitignore): precisa ser copiado para app/ml/ em cada ambiente.
ML_DIR = Path(__file__).resolve().parent.parent / "ml"
WEIGHTS_PATH = ML_DIR / "efficientnet_best.pt"
CLASSES_PATH = ML_DIR / "efficientnet_classes.json"

MODEL_NAME = "efficientnet-b0-adequacy-v1"
ADEQUATE_CLASS = "adequado"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Mesmo pré-processamento da avaliação no treino (build_transforms).
IMG_SIZE = 512
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

_model: nn.Module | None = None
_classes: list[str] | None = None


def _get_classes() -> list[str]:
    global _classes
    if _classes is None:
        with open(CLASSES_PATH, "r", encoding="utf-8") as f:
            classes = json.load(f)

        if ADEQUATE_CLASS not in classes:
            raise ValueError(
                f"{CLASSES_PATH.name} precisa conter a classe '{ADEQUATE_CLASS}'. Encontrado: {classes}"
            )

        _classes = classes
    return _classes


def _get_model() -> nn.Module:
    global _model
    if _model is None:
        if not WEIGHTS_PATH.exists():
            raise FileNotFoundError(
                f"Pesos do classificador de qualidade não encontrados em {WEIGHTS_PATH}. "
                "Copie o best.pt gerado por train_efficientnet.py para esse caminho."
            )

        model = efficientnet_b0(weights=None)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(_get_classes()))
        model.load_state_dict(
            torch.load(WEIGHTS_PATH, map_location=DEVICE, weights_only=True)
        )
        model.eval()
        _model = model.to(DEVICE)
    return _model


def classify_adequacy(image_bytes: bytes) -> dict:
    """
    Classifica a radiografia como adequada/inadequada com a EfficientNet-B0
    supervisionada. A decisão é o argmax das duas classes (limiar 0,5).

    `score` é a probabilidade de "adequado" em escala 0-100, então 50 é a
    fronteira da decisão. É a saída do softmax, sem calibração: serve para
    ordenar e comparar, não como percentual de certeza clínica.

    No conjunto de teste, o modelo teve acurácia de 77,9% e recall de 58,9%
    para "inadequado" — ele deixa passar parte das imagens ruins.
    """
    classes = _get_classes()

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = _TRANSFORM(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        probabilities = torch.softmax(_get_model()(tensor)[0], dim=0).cpu().tolist()

    predicted = max(range(len(classes)), key=lambda i: probabilities[i])
    label = classes[predicted]

    return {
        "model": MODEL_NAME,
        "label": label,
        "is_adequate": label == ADEQUATE_CLASS,
        "score": round(100 * probabilities[classes.index(ADEQUATE_CLASS)], 1),
        "confidence": round(probabilities[predicted], 4),
        "probabilities": {
            name: round(probability, 4) for name, probability in zip(classes, probabilities)
        },
    }
