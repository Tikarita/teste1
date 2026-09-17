# process_dataset_03.py
"""
Organiza o dataset 03 (Panoramic Dental X-rays With Segmented Mandibles V1),
ja copiado manualmente em AKTIA_DATASETS/03_Panoramic_Mandibles_V1/.

As "mascaras" (Segmentation1/, Segmentation2/ - 2 dentistas) sao, na
verdade, a imagem original com tudo fora da mandibula zerado (confirmado:
valores de pixel continuos tipo escala de cinza dentro da regiao, nao um
valor binario fixo) - nao mascaras binarias puras. Convertidas aqui para
bounding box (classe unica "mandibula") via limiar > 0.

Usa Segmentation1 (dentista 1) como anotacao principal - Segmentation2
(dentista 2) e preservada em raw/ para quem quiser comparar concordância
entre anotadores, mas nao duplicada no YOLO para nao contar a mesma imagem
duas vezes com dois rotulos de bbox ligeiramente diferentes.
"""
import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path("AKTIA_DATASETS/03_Panoramic_Mandibles_V1")
SRC = ROOT / "DentalPanoramicXrays"
RAW = ROOT / "raw"
IMAGES = ROOT / "images"
YOLO = ROOT / "yolo"
PROJECT_IMAGES = Path("dados") / "images"
PREFIX = "mnd_"

SPLIT_RATIOS = {"train": 0.760509, "valid": 0.084624, "test": 0.154867}
SPLIT_SEED = 42


def assign_splits(names: list) -> dict:
    shuffled = names[:]
    random.Random(SPLIT_SEED).shuffle(shuffled)
    n = len(shuffled)
    n_train = round(n * SPLIT_RATIOS["train"])
    n_valid = round(n * SPLIT_RATIOS["valid"])
    out = {}
    for fn in shuffled[:n_train]:
        out[fn] = "train"
    for fn in shuffled[n_train:n_train + n_valid]:
        out[fn] = "valid"
    for fn in shuffled[n_train + n_valid:]:
        out[fn] = "test"
    return out


def main():
    img_dir = SRC / "Images"
    mask_dir = SRC / "Segmentation1"
    files = sorted(img_dir.glob("*.png"))
    splits = assign_splits([p.name for p in files])

    for base in (RAW, IMAGES,
                 YOLO / "images" / "train", YOLO / "images" / "valid", YOLO / "images" / "test",
                 YOLO / "labels" / "train", YOLO / "labels" / "valid", YOLO / "labels" / "test"):
        base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, RAW / "DentalPanoramicXrays", dirs_exist_ok=True)

    n_ok = n_empty = 0
    for p in files:
        mask_path = mask_dir / p.name
        if not mask_path.exists():
            continue
        split = splits[p.name]

        mask = np.array(Image.open(mask_path).convert("L"))
        ys, xs = np.nonzero(mask > 0)
        img_w, img_h = Image.open(p).size

        shutil.copy2(p, IMAGES / p.name)
        shutil.copy2(p, YOLO / "images" / split / p.name)

        lines = []
        if len(xs) > 0:
            x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
            cx, cy = (x1 + x2) / 2 / img_w, (y1 + y2) / 2 / img_h
            w, h = (x2 - x1) / img_w, (y2 - y1) / img_h
            lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            n_ok += 1
        else:
            n_empty += 1

        with open(YOLO / "labels" / split / f"{p.stem}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

        proj_split = "valid" if split == "valid" else split
        dest = PROJECT_IMAGES / proj_split / f"{PREFIX}{p.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(p, dest)

    with open(YOLO / "data.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {YOLO.resolve()}\ntrain: images/train\nval: images/valid\ntest: images/test\n")
        f.write("nc: 1\nnames:\n- 'mandibula'\n")

    print(f"Dataset 03: {n_ok} imagens com bbox de mandibula, {n_empty} sem regiao detectada")
    print(f"data.yaml: {YOLO / 'data.yaml'}")
    print("Segmentation2 (2o dentista) preservada em raw/ para referencia, nao usada no YOLO.")


if __name__ == "__main__":
    main()
