# check_oval_bias.py
"""
Verifica se o formato oval/retangular das radiografias esta correlacionado
com a fonte da imagem e com o rotulo de qualidade (adequado/inadequado),
o que indicaria risco de atalho espurio no EfficientNet (o modelo aprender
"cantos pretos = inadequado" em vez de qualidade de verdade).

Deteccao de oval: mede a intensidade media dos 4 cantos da imagem (patches
pequenos). Se os 4 cantos forem bem escuros, classifica como "oval"
(area de exposicao colimada, cantos fora da area ficam pretos). Caso
contrario, "retangular" (exposicao cobre a imagem inteira).
"""
import csv
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from PIL import Image

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DARK_THRESHOLD = 15    # intensidade media abaixo disso = canto "preto"
LIGHT_THRESHOLD = 245  # intensidade media acima disso = canto "branco"
CORNER_FRAC = 0.04     # tamanho do patch de canto, fracao da imagem

PREFIX_SOURCE = {
    "nd_": "06_Tufts",
    "pdx_": "01_Panoramic_Dental_Xray",
    "mnd_": "03_Mandibles_V1",
    "dr_": "04_Dental_Radiography",
}


def source_of(name: str) -> str:
    for pfx, src in PREFIX_SOURCE.items():
        if name.startswith(pfx):
            return src
    return "00_original_projeto"


def is_oval(img: Image.Image) -> bool:
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    ch, cw = max(1, int(h * CORNER_FRAC)), max(1, int(w * CORNER_FRAC))
    corners = [
        arr[:ch, :cw], arr[:ch, -cw:],
        arr[-ch:, :cw], arr[-ch:, -cw:],
    ]
    means = [c.mean() for c in corners]
    return all(m < DARK_THRESHOLD for m in means) or all(m > LIGHT_THRESHOLD for m in means)


def main():
    labels = {}
    with open("dados/labels_qualidade.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            labels[row["image_path"]] = row["label"]

    rows = []
    for split in ("train", "valid", "test"):
        for p in Path(f"dados/images/{split}").iterdir():
            try:
                img = Image.open(p)
                shape = "oval" if is_oval(img) else "retangular"
            except Exception as e:
                continue
            key = f"images/{split}/{p.name}"
            rows.append({
                "source": source_of(p.name),
                "shape": shape,
                "label": labels.get(key, "SEM_ROTULO"),
            })

    print(f"Total de imagens analisadas: {len(rows)}\n")

    print("=== Formato x Fonte ===")
    by_source = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_source[r["source"]][r["shape"]] += 1
    for src in sorted(by_source):
        d = by_source[src]
        total = sum(d.values())
        oval_pct = 100 * d.get("oval", 0) / total
        print(f"  {src:30s} oval={d.get('oval',0):5d} ({oval_pct:5.1f}%)  retangular={d.get('retangular',0):5d}  total={total}")

    print("\n=== Formato x Rotulo de qualidade (so imagens ja rotuladas) ===")
    by_shape_label = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["label"] == "SEM_ROTULO":
            continue
        by_shape_label[r["shape"]][r["label"]] += 1
    for shape in sorted(by_shape_label):
        d = by_shape_label[shape]
        total = sum(d.values())
        adeq_pct = 100 * d.get("adequado", 0) / total if total else 0
        print(f"  {shape:12s} adequado={d.get('adequado',0):5d} ({adeq_pct:5.1f}%)  inadequado={d.get('inadequado',0):5d}  total={total}")

    print("\n=== Formato x Fonte x Rotulo (tabela completa, so rotuladas) ===")
    by_all = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["label"] == "SEM_ROTULO":
            continue
        by_all[(r["source"], r["shape"])][r["label"]] += 1
    for key in sorted(by_all):
        src, shape = key
        d = by_all[key]
        total = sum(d.values())
        adeq_pct = 100 * d.get("adequado", 0) / total if total else 0
        print(f"  {src:30s} {shape:12s} adequado={d.get('adequado',0):5d} ({adeq_pct:5.1f}%)  inadequado={d.get('inadequado',0):5d}  total={total}")


if __name__ == "__main__":
    main()
