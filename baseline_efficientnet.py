# baseline_efficientnet.py
"""
Classificador adequado/inadequado SEM rótulos, para usar enquanto o
dataset rotulado (dados/panoramicas/{train,valid,test}/{adequado,
inadequado}) não existe. Depois que houver labels de verdade, treine
train_efficientnet.py — este script aqui é só um baseline provisório.

Como funciona (detecção de anomalia com features da EfficientNet):
1. Extrai embeddings (features da penúltima camada da EfficientNet-B0,
   pré-treinada na ImageNet) de um conjunto de referência de radiografias
   "típicas" — por padrão, dados/images/train (o mesmo corpus usado no
   YOLO, sem rótulo de qualidade, mas representativo do que uma panorâmica
   normal parece).
2. Calcula o centróide desses embeddings e a distância de cada imagem de
   referência até ele. O percentil superior dessas distâncias vira o
   limiar de corte.
3. Para uma imagem nova, mede a distância do embedding dela ao centróide.
   Quanto mais longe do "normal", mais provável que seja inadequada
   (borrada, cortada, com artefato etc.) — já que a EfficientNet foi
   treinada para captar textura/forma/padrões visuais gerais.

Isso é uma aproximação heurística, não um classificador supervisionado:
espere bem menos precisão do que um modelo treinado com rótulos reais.

Uso:
    python baseline_efficientnet.py                    # demo rápida
    python baseline_efficientnet.py fit --ref-dir DIR   # ajusta a referência
    python baseline_efficientnet.py predict IMAGEM.jpg  # classifica 1 imagem

Dependências: torch, torchvision, pillow, numpy
    pip install torch torchvision pillow numpy

Na primeira execução, o torchvision baixa os pesos da EfficientNet-B0
pré-treinada na ImageNet (precisa de internet uma única vez; depois fica
em cache local).
"""
import argparse
import json
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from config import DATA_DIR, EFFICIENTNET_CONFIG
from train_efficientnet import DEVICE, build_feature_extractor, build_transforms

REFERENCE_PATH = Path("runs_qc") / "efficientnet" / "baseline_reference.json"
DEFAULT_REF_DIR = str(DATA_DIR / "images" / "train")
DEFAULT_PREVIEW_DIR = str(DATA_DIR / "images" / "test")
IMG_SIZE = EFFICIENTNET_CONFIG["img_size"]

_model = None


def get_model():
    global _model
    if _model is None:
        _model = build_feature_extractor()
    return _model


class ImageListDataset(Dataset):
    def __init__(self, paths, transform):
        self.paths = paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        image = Image.open(self.paths[idx]).convert("RGB")
        return self.transform(image)


def list_images(directory: str, max_images: int = None, seed: int = 42) -> list:
    paths = sorted(Path(directory).glob("*.jpg"))
    if max_images and len(paths) > max_images:
        paths = random.Random(seed).sample(paths, max_images)
    return paths


def extract_embeddings(paths: list, batch_size: int = 16) -> np.ndarray:
    _, eval_tf = build_transforms(IMG_SIZE)
    loader = DataLoader(ImageListDataset(paths, eval_tf), batch_size=batch_size, shuffle=False)

    model = get_model()
    embeddings = []
    with torch.no_grad():
        for images in loader:
            feats = model(images.to(DEVICE)).cpu().numpy()
            embeddings.append(feats)

    embeddings = np.concatenate(embeddings, axis=0)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / np.clip(norms, 1e-8, None)


def fit_reference(ref_dir: str = DEFAULT_REF_DIR, max_ref: int = 300, percentile: float = 90.0) -> dict:
    paths = list_images(ref_dir, max_ref)
    if not paths:
        raise FileNotFoundError(f"Nenhuma imagem .jpg encontrada em {ref_dir}")

    print(f"Extraindo embeddings de {len(paths)} imagens de referência de {ref_dir}...")
    embeddings = extract_embeddings(paths)

    centroid = embeddings.mean(axis=0)
    distances = np.linalg.norm(embeddings - centroid, axis=1)
    threshold = float(np.percentile(distances, percentile))

    reference = {
        "centroid": centroid.tolist(),
        "threshold": threshold,
        "percentile": percentile,
        "ref_dir": ref_dir,
        "n_ref_images": len(paths),
        "distance_stats": {
            "min": float(distances.min()),
            "median": float(np.median(distances)),
            "max": float(distances.max()),
        },
    }

    REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REFERENCE_PATH, "w", encoding="utf-8") as f:
        json.dump(reference, f)

    print(f"Referência salva em {REFERENCE_PATH}")
    print(f"Limiar (percentil {percentile}): distância <= {threshold:.4f} -> adequado\n")
    return reference


def load_reference() -> dict:
    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"{REFERENCE_PATH} não encontrado. Rode antes: "
            "python baseline_efficientnet.py fit"
        )
    with open(REFERENCE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def predict_image(image_path: str, reference: dict = None) -> dict:
    reference = reference or load_reference()
    centroid = np.array(reference["centroid"])
    threshold = reference["threshold"]

    embedding = extract_embeddings([Path(image_path)])[0]
    distance = float(np.linalg.norm(embedding - centroid))
    is_adequate = distance <= threshold
    score = round(max(0.0, min(100.0, 100 * (1 - distance / (2 * threshold)))), 1)

    return {
        "image": str(image_path),
        "label": "adequado" if is_adequate else "inadequado",
        "score": score,
        "distance": round(distance, 4),
        "threshold": round(threshold, 4),
    }


def _run_demo():
    print(f"Dispositivo: {DEVICE}\n")
    reference = fit_reference(DEFAULT_REF_DIR, max_ref=200)

    preview_paths = list_images(DEFAULT_PREVIEW_DIR, max_images=8)
    print(f"Classificando {len(preview_paths)} imagens de exemplo de {DEFAULT_PREVIEW_DIR}:\n")
    for path in preview_paths:
        result = predict_image(str(path), reference)
        print(f"  {path.name:>12} -> {result['label']:<12} (score={result['score']:>5}, dist={result['distance']})")

    print(
        "\nEsse resultado é heurístico (sem rótulos reais) — sirva como ponto de "
        "partida. Quando tiver imagens rotuladas adequado/inadequado, treine "
        "train_efficientnet.py para um modelo supervisionado de verdade."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command")

    fit_parser = subparsers.add_parser("fit", help="Ajusta a referência de normalidade")
    fit_parser.add_argument("--ref-dir", default=DEFAULT_REF_DIR)
    fit_parser.add_argument("--max-ref", type=int, default=300)
    fit_parser.add_argument("--percentile", type=float, default=90.0)

    predict_parser = subparsers.add_parser("predict", help="Classifica uma imagem")
    predict_parser.add_argument("image")

    args = parser.parse_args()

    if args.command == "fit":
        fit_reference(args.ref_dir, args.max_ref, args.percentile)
    elif args.command == "predict":
        print(json.dumps(predict_image(args.image), ensure_ascii=False, indent=2))
    else:
        _run_demo()
