# dataset_qc.py
import csv
import os
import shutil
from pathlib import Path
import cv2
import numpy as np
from config import DATA_DIR, YOLO_CLASSES

LABELS_CSV = DATA_DIR / "labels_qualidade.csv"
PANORAMICAS_DIR = DATA_DIR / "panoramicas"


def build_imagefolder_from_labels(
    labels_csv: Path = LABELS_CSV,
    output_dir: Path = PANORAMICAS_DIR,
    copy: bool = True,
) -> None:
    """
    Lê dados/labels_qualidade.csv (gerado por label_tool.py) e organiza as
    imagens em dados/panoramicas/{train,valid,test}/{adequado,inadequado}/,
    a estrutura ImageFolder que train_efficientnet.py espera.

    copy=True copia os arquivos (padrão, seguro); copy=False usa symlink
    (mais rápido, economiza espaço, mas exige permissão no Windows).
    """
    if not labels_csv.exists():
        raise FileNotFoundError(
            f"{labels_csv} não existe. Rotule as imagens antes com label_tool.py."
        )

    with open(labels_csv, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    contagem = {}
    ausentes = []
    for row in rows:
        split, label = row["split"], row["label"]
        src = DATA_DIR / row["image_path"]
        if not src.exists():
            ausentes.append(str(src))
            continue

        dest_dir = output_dir / split / label
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        if copy:
            shutil.copy2(src, dest)
        else:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(src.resolve())

        contagem[(split, label)] = contagem.get((split, label), 0) + 1

    print(f"Dataset organizado em {output_dir}:")
    for (split, label), n in sorted(contagem.items()):
        print(f"  {split}/{label}: {n} imagens")
    if ausentes:
        print(f"\n{len(ausentes)} imagens listadas no CSV não foram encontradas em disco:")
        for p in ausentes[:10]:
            print(f"  {p}")
        if len(ausentes) > 10:
            print(f"  ... e mais {len(ausentes) - 10}")


def prepare_qc_dataset(
    source_dir: str,
    output_dir: str,
    split_ratio: tuple = (0.7, 0.15, 0.15)
):
    """
    Prepara dataset para treinamento de QC.
    source_dir: diretório com imagens e labels YOLO
    output_dir: diretório organizado para treino
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    images_dir = output / "images"
    labels_dir = output / "labels"

    for split in ["train", "valid", "test"]:
        (images_dir / split).mkdir(parents=True, exist_ok=True)
        (labels_dir / split).mkdir(parents=True, exist_ok=True)

    # Copia arquivos organizando por split
    # Implemente sua lógica de split aqui
    print("Dataset preparado com sucesso!")

def generate_quality_labels(
    images_dir: str,
    output_csv: str,
    yolo_detections: dict = None
):
    """
    Gera labels de qualidade (aceitável/inaceitável) baseado em:
    - Critérios clínicos
    - Detecções YOLO
    - Análise de imagem
    """
    import pandas as pd
    
    records = []
    
    for img_path in Path(images_dir).glob("*.jpg"):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        # Análise de qualidade baseada em regras
        score = analyze_image_quality(img, yolo_detections)
        label = "aceitavel" if score >= 0.6 else "inaceitavel"
        
        records.append({
            "image_path": str(img_path),
            "quality_label": label,
            "quality_score": score
        })
    
    df = pd.DataFrame(records)
    df.to_csv(output_csv, index=False)
    print(f"Labels gerados: {output_csv}")
    return df

def analyze_image_quality(img: np.ndarray, yolo_detections: dict = None) -> float:
    """
    Analisa qualidade da imagem com base em múltiplos critérios.
    Retorna score entre 0 (péssima) e 1 (excelente).
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    scores = {}
    
    # 1. Nitidez (Laplacian variance)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    scores["nitidez"] = min(1.0, lap_var / 150.0)
    
    # 2. Simetria lateral
    left = gray[:, :w//2]
    right = cv2.flip(gray[:, w//2:], 1)
    if left.shape == right.shape:
        diff = np.abs(left.astype(float) - right.astype(float))
        scores["simetria"] = 1.0 - (np.mean(diff) / 128.0)
    else:
        scores["simetria"] = 0.5
    
    # 3. Enquadramento (detecção de bordas escuras)
    bordas = {
        "topo": np.mean(gray[:int(h*0.04), :]),
        "base": np.mean(gray[int(h*0.96):, :]),
        "esq": np.mean(gray[:, :int(w*0.04)]),
        "dir": np.mean(gray[:, int(w*0.96):])
    }
    bordas_escuras = sum(1 for v in bordas.values() if v < 18)
    scores["enquadramento"] = 1.0 if bordas_escuras == 0 else 0.5 if bordas_escuras <= 2 else 0.2
    
    # 4. Penalidade por detecções YOLO
    yolo_penalty = 0.0
    if yolo_detections:
        critical = ["cone_cut", "coluna_sobreposta"]
        for det in yolo_detections:
            if det.get("class") in critical:
                yolo_penalty += 0.15
    
    # Score final ponderado
    weights = {
        "nitidez": 0.35,
        "simetria": 0.25,
        "enquadramento": 0.40
    }
    
    weighted_score = sum(scores[k] * weights[k] for k in scores)
    final_score = max(0.0, weighted_score - yolo_penalty)
    
    return final_score

if __name__ == "__main__":
    build_imagefolder_from_labels()