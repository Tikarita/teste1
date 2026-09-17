# process_dataset_04.py
"""
Organiza o dataset 04 (Dental Radiography, Kaggle/Roboflow) ja baixado em
AKTIA_DATASETS/04_Dental_Radiography/{train,valid,test}/ (formato Roboflow:
imagens + _annotations.csv por split, pascal-voc-style).

- Move os arquivos originais para raw/ (preserva a estrutura/split do Roboflow
  tal como foi construida na origem - nao misturar train/valid/test).
- Converte as anotacoes para YOLO txt em yolo/images|labels/{train,valid,test}.
- Copia as mesmas imagens (com prefixo "dr_") para dados/images/{split} do
  projeto principal, para entrarem na fila do label_tool.py (nenhuma imagem
  publica vem com rotulo adequado/inadequado pronto).
- Popula AKTIA_DATASETS/YOLO/ (pool mestre) com essas classes, ja que e a
  primeira fonte nova com anotacoes de patologia claras e completas.

Classes (confirmadas no CSV): Cavity, Fillings, Impacted Tooth, Implant
"""
import csv
import shutil
import sys
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SRC_ROOT = Path("AKTIA_DATASETS/04_Dental_Radiography")
RAW_DIR = SRC_ROOT / "raw"
DS_IMAGES = SRC_ROOT / "images"
DS_YOLO = SRC_ROOT / "yolo"
MASTER_YOLO = Path("AKTIA_DATASETS/YOLO")
PROJECT_IMAGES = Path("dados") / "images"

SPLITS = ["train", "valid", "test"]
SPLIT_MAP = {"train": "train", "valid": "val", "test": "test"}  # nome usado no pool mestre
CLASS_NAMES = ["Cavity", "Fillings", "Impacted Tooth", "Implant"]
CLASS_TO_ID = {c: i for i, c in enumerate(CLASS_NAMES)}
PREFIX = "dr_"


def convert_split(split: str):
    src_dir = SRC_ROOT / split
    csv_path = src_dir / "_annotations.csv"
    if not csv_path.exists():
        print(f"  [{split}] sem _annotations.csv, pulando")
        return 0, 0

    boxes_by_image = defaultdict(list)
    dims = {}
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fn = row["filename"]
            w, h = int(row["width"]), int(row["height"])
            dims[fn] = (w, h)
            cls = row["class"]
            xmin, ymin, xmax, ymax = (int(row["xmin"]), int(row["ymin"]), int(row["xmax"]), int(row["ymax"]))
            cx = ((xmin + xmax) / 2) / w
            cy = ((ymin + ymax) / 2) / h
            bw = (xmax - xmin) / w
            bh = (ymax - ymin) / h
            boxes_by_image[fn].append(f"{CLASS_TO_ID[cls]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    myolo_split = SPLIT_MAP[split]
    for sub in (DS_IMAGES / split, DS_YOLO / "images" / split, DS_YOLO / "labels" / split,
                MASTER_YOLO / "images" / myolo_split, MASTER_YOLO / "labels" / myolo_split,
                RAW_DIR / split):
        sub.mkdir(parents=True, exist_ok=True)

    n_imgs = 0
    for fn in dims:
        src_img = src_dir / fn
        if not src_img.exists():
            continue
        # raw/ preserva original
        shutil.copy2(src_img, RAW_DIR / split / fn)
        # images/ + yolo/ do dataset
        shutil.copy2(src_img, DS_IMAGES / split / fn)
        with open(DS_YOLO / "labels" / split / f"{Path(fn).stem}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(boxes_by_image[fn]) + "\n")
        shutil.copy2(src_img, DS_YOLO / "images" / split / fn)
        # pool mestre AKTIA_DATASETS/YOLO
        shutil.copy2(src_img, MASTER_YOLO / "images" / myolo_split / fn)
        with open(MASTER_YOLO / "labels" / myolo_split / f"{Path(fn).stem}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(boxes_by_image[fn]) + "\n")
        # dados/images do projeto principal, para fila de classificacao manual (QC)
        proj_split = "valid" if split == "valid" else split
        dest = PROJECT_IMAGES / proj_split / f"{PREFIX}{fn}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src_img, dest)
        n_imgs += 1

    # csv original tambem vai pro raw/
    shutil.copy2(csv_path, RAW_DIR / split / "_annotations.csv")

    n_boxes = sum(len(v) for v in boxes_by_image.values())
    print(f"  [{split}] {n_imgs} imagens, {n_boxes} caixas")
    return n_imgs, n_boxes


def main():
    print("Processando dataset 04 (Dental Radiography)...")
    total_imgs = total_boxes = 0
    for split in SPLITS:
        ni, nb = convert_split(split)
        total_imgs += ni
        total_boxes += nb

    with open(DS_YOLO / "data.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {DS_YOLO.resolve()}\n")
        f.write("train: images/train\nval: images/valid\ntest: images/test\n")
        f.write(f"nc: {len(CLASS_NAMES)}\nnames:\n")
        for c in CLASS_NAMES:
            f.write(f"- '{c}'\n")

    # remove as pastas soltas originais (train/valid/test na raiz do dataset) apos copiar pra raw/
    for split in SPLITS:
        loose = SRC_ROOT / split
        if loose.exists() and loose.resolve() != RAW_DIR.resolve():
            shutil.rmtree(loose)

    with open(MASTER_YOLO / "data.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {MASTER_YOLO.resolve()}\n")
        f.write("train: images/train\nval: images/val\ntest: images/test\n")
        f.write(f"nc: {len(CLASS_NAMES)}\nnames:\n")
        for c in CLASS_NAMES:
            f.write(f"- '{c}'\n")
        f.write("# fonte: 04_Dental_Radiography (unica fonte com anotacoes de patologia prontas ate agora)\n")

    print(f"\nTotal: {total_imgs} imagens, {total_boxes} caixas")
    print(f"data.yaml (dataset): {DS_YOLO / 'data.yaml'}")
    print(f"data.yaml (pool mestre): {MASTER_YOLO / 'data.yaml'}")


if __name__ == "__main__":
    main()
