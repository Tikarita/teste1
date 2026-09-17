# build_teeth_numbering_dataset.py
"""
Converte a base "Novos dados" (radiografias + teeth_bbox.json, com um bbox por
dente numerado — 1-32 permanentes, A-T decíduos) para um dataset YOLO
separado em dados_dentes/, no mesmo formato usado em dados/ (images/labels
por split + data.yaml).

É uma tarefa diferente da detecção de achados clínicos em dados/data.yaml
(14 classes tipo CAR/END/IMP): aqui cada classe é um número de dente, não uma
patologia. Por isso fica em pasta própria, sem misturar com dados/labels/.

Formato do bbox no JSON de origem: [y1, x1, y2, x2] (eixos invertidos em
relação ao [x1,y1,x2,y2] usual) — confirmado comparando com o tamanho real
das imagens (1615x840): y2 nunca passa de 840, x2 nunca passa de 1615.

Uso:
    python build_teeth_numbering_dataset.py
"""
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SOURCE_DIR = Path(r"C:\Users\24011603\Downloads\Novos dados")
RADIOGRAPHS_DIR = SOURCE_DIR / "Radiographs"
BBOX_JSON = SOURCE_DIR / "Segmentation" / "Segmentation" / "teeth_bbox.json"

OUTPUT_DIR = Path("dados_dentes")
MIN_BOX_SIZE = 3  # px — descarta caixas-ponto de dentes ausentes/não-erupcionados

# Mesma proporção train/valid/test já usada em dados/images/{split}
SPLIT_RATIOS = {"train": 0.760509, "valid": 0.084624, "test": 0.154867}
SPLIT_SEED = 42


def build_class_list() -> list[str]:
    numeric = [str(i) for i in range(1, 33)]       # dentes permanentes 1-32
    letters = [chr(c) for c in range(ord("A"), ord("T") + 1)]  # decíduos A-T
    return numeric + letters


def assign_splits(filenames: list[str]) -> dict[str, str]:
    shuffled = filenames[:]
    random.Random(SPLIT_SEED).shuffle(shuffled)

    n = len(shuffled)
    n_train = round(n * SPLIT_RATIOS["train"])
    n_valid = round(n * SPLIT_RATIOS["valid"])

    assignment = {}
    for fn in shuffled[:n_train]:
        assignment[fn] = "train"
    for fn in shuffled[n_train:n_train + n_valid]:
        assignment[fn] = "valid"
    for fn in shuffled[n_train + n_valid:]:
        assignment[fn] = "test"
    return assignment


def main() -> None:
    if not BBOX_JSON.exists():
        raise FileNotFoundError(f"Não encontrei {BBOX_JSON}")

    with open(BBOX_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    class_names = build_class_list()
    class_to_id = {name: i for i, name in enumerate(class_names)}

    files_on_disk = {p.name.lower(): p for p in RADIOGRAPHS_DIR.iterdir()}
    splits = assign_splits([e["External ID"] for e in entries])

    for split in ("train", "valid", "test"):
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    contagem_imgs = {"train": 0, "valid": 0, "test": 0}
    contagem_boxes = {"train": 0, "valid": 0, "test": 0}
    descartadas = 0
    ausentes = []

    for entry in entries:
        ext_id = entry["External ID"]
        src_path = files_on_disk.get(ext_id.lower())
        if src_path is None:
            ausentes.append(ext_id)
            continue

        split = splits[ext_id]
        img_w, img_h = Image.open(src_path).size

        lines = []
        for obj in entry["Label"]["objects"]:
            title = obj["title"]
            if title not in class_to_id:
                continue
            y1, x1, y2, x2 = obj["bounding box"]  # eixos invertidos na origem
            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))

            if x2 - x1 < MIN_BOX_SIZE or y2 - y1 < MIN_BOX_SIZE:
                descartadas += 1
                continue

            cx = ((x1 + x2) / 2) / img_w
            cy = ((y1 + y2) / 2) / img_h
            w = (x2 - x1) / img_w
            h = (y2 - y1) / img_h
            lines.append(f"{class_to_id[title]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        dest_name = src_path.stem + ".jpg"
        shutil.copy2(src_path, OUTPUT_DIR / "images" / split / dest_name)
        with open(OUTPUT_DIR / "labels" / split / f"{src_path.stem}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

        contagem_imgs[split] += 1
        contagem_boxes[split] += len(lines)

    data_yaml = OUTPUT_DIR / "data.yaml"
    with open(data_yaml, "w", encoding="utf-8") as f:
        f.write(f"path: {OUTPUT_DIR.resolve()}\n")
        f.write("train: images/train\n")
        f.write("val: images/valid\n")
        f.write("test: images/test\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write("names:\n")
        for name in class_names:
            f.write(f"- '{name}'\n")

    print(f"Dataset de numeração de dentes gerado em {OUTPUT_DIR.resolve()}")
    for split in ("train", "valid", "test"):
        print(f"  {split}: {contagem_imgs[split]} imagens, {contagem_boxes[split]} caixas")
    print(f"\n{descartadas} caixas descartadas (dente ausente/não-erupcionado, <{MIN_BOX_SIZE}px)")
    if ausentes:
        print(f"{len(ausentes)} entradas do JSON sem imagem correspondente em Radiographs/: {ausentes[:10]}")
    print(f"\ndata.yaml escrito em {data_yaml}")


if __name__ == "__main__":
    main()
