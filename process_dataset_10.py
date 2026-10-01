# process_dataset_10.py
"""
Organiza o dataset 10 (Panoramic radiography database, Zenodo 4457648),
extraido pelo usuario direto na raiz de AKTIA_DATASETS/10_Panoramic_Radiography_Asuncion/.

598 imagens, sem anotacao nenhuma - so serve como fonte de imagem para o
EfficientNet (qualidade). Copia para raw/ (preserva original), images/, e
para dados/images/{split} do projeto principal, para entrar na fila do
label_tool.py (prefixo "asu_").
"""
import random
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path("AKTIA_DATASETS/10_Panoramic_Radiography_Asuncion")
RAW = ROOT / "raw"
IMAGES = ROOT / "images"
PROJECT_IMAGES = Path("dados") / "images"
PREFIX = "asu_"

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
    files = sorted(ROOT.glob("*.jpg"))
    splits = assign_splits([p.name for p in files])

    RAW.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    n = 0
    for p in files:
        split = splits[p.name]
        shutil.copy2(p, RAW / p.name)
        shutil.copy2(p, IMAGES / p.name)

        proj_split = "valid" if split == "valid" else split
        dest = PROJECT_IMAGES / proj_split / f"{PREFIX}{p.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(p, dest)
        n += 1

    print(f"Dataset 10: {n} imagens copiadas para raw/, images/ e dados/images/ (prefixo '{PREFIX}')")
    print("Sem anotacao - so alimenta a fila de classificacao de qualidade (label_tool.py).")


if __name__ == "__main__":
    main()
