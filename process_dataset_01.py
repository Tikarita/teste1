# process_dataset_01.py
"""
Organiza o dataset 01 (Panoramic Dental Xray, Mendeley 73n3kz2k4k v3), ja
extraido manualmente em AKTIA_DATASETS/01_Panoramic_Dental_Xray/.

Contem 3 sub-partes distintas, confirmadas por inspecao direta dos arquivos
(a descricao da pagina Mendeley nao batia exatamente com os nomes dos .rar):

  parte 1: 107 imagens soltas + annotations.json (VIA) - instance segmentation
           de dentes, SEM classe por dente (atributo "Teeth" vazio em todas
           as 772 regioes) -> vira 1 classe YOLO: "dente".
  parte 2: extracted_secondpart/{train,valid,test} - 60 imagens com anotacao
           COCO (8 tipos de dente: canine, central incisor, first molar,
           first premolar, lateral incisor, second molar, second premolar,
           third molar, + categoria generica "dental").
  parte 3: extracted_thirdpart - 54 imagens em alta resolucao, SEM anotacao.
           extracted_secondpanoramic contem os MESMOS 54 arquivos (hash
           identico, confirmado) - e descartado aqui para nao duplicar.

Todas as imagens (independente de terem anotacao YOLO ou nao) tambem sao
copiadas para dados/images/{split} do projeto principal, pois nenhuma vem
com rotulo adequado/inadequado - precisam passar pelo label_tool.py.
"""
import json
import random
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path("AKTIA_DATASETS/01_Panoramic_Dental_Xray")
SRC = ROOT / "Panoramic Dental Xray Dataset"
RAW = ROOT / "raw"
IMAGES = ROOT / "images"
YOLO = ROOT / "yolo"
PROJECT_IMAGES = Path("dados") / "images"
PREFIX = "pdx_"

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


def to_yolo_bbox(xs, ys, img_w, img_h):
    x1, x2 = max(0, min(xs)), min(img_w, max(xs))
    y1, y2 = max(0, min(ys)), min(img_h, max(ys))
    cx, cy = (x1 + x2) / 2 / img_w, (y1 + y2) / 2 / img_h
    w, h = (x2 - x1) / img_w, (y2 - y1) / img_h
    return cx, cy, w, h


def add_to_project_queue(img_path: Path, split: str, new_name: str):
    proj_split = "valid" if split == "valid" else split
    dest = PROJECT_IMAGES / proj_split / new_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(img_path, dest)


def process_part1():
    """VIA polygons -> 1 classe 'dente'."""
    from PIL import Image

    with open(SRC / "annotations.json", encoding="utf-8") as f:
        via = json.load(f)

    names = [e["filename"] for e in via["_via_img_metadata"].values()]
    splits = assign_splits(names)

    (RAW / "part1_instance_seg").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "annotations.json", RAW / "part1_instance_seg" / "annotations.json")

    n_boxes = 0
    for entry in via["_via_img_metadata"].values():
        fn = entry["filename"]
        src_img = SRC / fn
        if not src_img.exists():
            continue
        split = splits[fn]
        shutil.copy2(src_img, RAW / "part1_instance_seg" / fn)

        img_w, img_h = Image.open(src_img).size
        lines = []
        for r in entry.get("regions", []):
            shape = r["shape_attributes"]
            xs = shape.get("all_points_x")
            ys = shape.get("all_points_y")
            if not xs or not ys:
                continue
            cx, cy, w, h = to_yolo_bbox(xs, ys, img_w, img_h)
            if w <= 0 or h <= 0:
                continue
            lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            n_boxes += 1

        for base in (IMAGES / "part1", YOLO / "images" / split):
            base.mkdir(parents=True, exist_ok=True)
        (YOLO / "labels" / split).mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_img, IMAGES / "part1" / fn)
        shutil.copy2(src_img, YOLO / "images" / split / fn)
        with open(YOLO / "labels" / split / f"{Path(fn).stem}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

        add_to_project_queue(src_img, split, f"{PREFIX}p1_{fn}")

    print(f"  parte 1: {len(names)} imagens, {n_boxes} dentes (classe unica 'dente')")
    with open(YOLO / "part1_data.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {YOLO.resolve()}\ntrain: images/train\nval: images/valid\ntest: images/test\n")
        f.write("nc: 1\nnames:\n- 'dente'\n")


def process_part2():
    """COCO -> 8 tipos de dente + 'dental' generico."""
    coco_root = SRC / "extracted_secondpart"
    (RAW / "part2_tooth_type").mkdir(parents=True, exist_ok=True)

    total_imgs = total_boxes = 0
    class_names = None
    for split_src in ("train", "valid", "test"):
        ann_path = coco_root / split_src / "_annotations.coco.json"
        if not ann_path.exists():
            continue
        with open(ann_path, encoding="utf-8") as f:
            coco = json.load(f)
        cats = {c["id"]: c["name"] for c in coco["categories"]}
        if class_names is None:
            class_names = [cats[i] for i in sorted(cats)]
            id_map = {name: idx for idx, name in enumerate(class_names)}

        images_by_id = {im["id"]: im for im in coco["images"]}
        anns_by_img = {}
        for ann in coco["annotations"]:
            anns_by_img.setdefault(ann["image_id"], []).append(ann)

        split = "valid" if split_src == "valid" else split_src
        img_dir = coco_root / split_src / "imgs"
        for base in (IMAGES / "part2", YOLO / "images" / split):
            base.mkdir(parents=True, exist_ok=True)
        (YOLO / "labels" / split).mkdir(parents=True, exist_ok=True)
        raw_split_dir = RAW / "part2_tooth_type" / split_src
        raw_split_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ann_path, raw_split_dir / "_annotations.coco.json")

        for img_id, im in images_by_id.items():
            fn = im["file_name"]
            src_img = img_dir / fn
            if not src_img.exists():
                continue
            shutil.copy2(src_img, raw_split_dir / fn)
            shutil.copy2(src_img, IMAGES / "part2" / fn)
            shutil.copy2(src_img, YOLO / "images" / split / fn)

            lines = []
            for ann in anns_by_img.get(img_id, []):
                x, y, w, h = ann["bbox"]
                cx = (x + w / 2) / im["width"]
                cy = (y + h / 2) / im["height"]
                nw, nh = w / im["width"], h / im["height"]
                cat_name = cats[ann["category_id"]]
                lines.append(f"{id_map[cat_name]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
            with open(YOLO / "labels" / split / f"{Path(fn).stem}.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))

            add_to_project_queue(src_img, split, f"{PREFIX}p2_{fn}")
            total_imgs += 1
            total_boxes += len(lines)

    print(f"  parte 2: {total_imgs} imagens, {total_boxes} caixas, classes: {class_names}")
    with open(YOLO / "part2_data.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {YOLO.resolve()}\ntrain: images/train\nval: images/valid\ntest: images/test\n")
        f.write(f"nc: {len(class_names)}\nnames:\n")
        for c in class_names:
            f.write(f"- '{c}'\n")


def process_part3():
    """54 imagens em alta resolucao, sem anotacao (descarta a copia duplicada)."""
    src_dir = SRC / "extracted_thirdpart" / "secondpanoramicdataset"
    files = sorted(src_dir.glob("*.jpg"))
    splits = assign_splits([p.name for p in files])

    raw_dir = RAW / "part3_highres_no_annotation"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (IMAGES / "part3").mkdir(parents=True, exist_ok=True)

    for p in files:
        split = splits[p.name]
        shutil.copy2(p, raw_dir / p.name)
        shutil.copy2(p, IMAGES / "part3" / p.name)
        add_to_project_queue(p, split, f"{PREFIX}p3_{p.name}")

    print(f"  parte 3: {len(files)} imagens (sem anotacao) - copia duplicada em extracted_secondpanoramic foi ignorada")


def main():
    print("Processando dataset 01 (Panoramic Dental Xray)...")
    process_part1()
    process_part2()
    process_part3()
    print("\nConcluido. Copias preservadas em raw/part{1,2,3}_*/")
    print("Os arquivos originais (.rar, jpgs soltos) continuam em "
          f"'{SRC}' - nao foram apagados, so copiados.")


if __name__ == "__main__":
    main()
