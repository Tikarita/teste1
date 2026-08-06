# dataset_qc.py
import os
import shutil
from pathlib import Path
import cv2
import numpy as np
from config import DATA_DIR, YOLO_CLASSES

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
    # Exemplo de uso
    generate_quality_labels(
        images_dir="dados/panoramicas/train",
        output_csv="dados/quality_labels_train.csv"
    )