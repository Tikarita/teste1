# add_novos_dados_images.py
"""
Copia as 1000 radiografias de "Novos dados/Radiographs" para
dados/images/{train,valid,test}, prefixando o nome com "nd_" para não
sobrescrever os arquivos que já existem lá — 997 dos 1000 nomes originais
(ex.: 368.jpg, 247.jpg) colidem com imagens já rotuladas em dados/images,
mas são radiografias diferentes (resolução 1615x840 vs ~2652x1536 das atuais).

Usa a mesma proporção train/valid/test já usada em dados/images (a mesma
lógica de build_teeth_numbering_dataset.py), então a mesma imagem cai no
mesmo split nas duas bases (dados/ e dados_dentes/).

Depois de rodar, classifique com:
    python label_tool.py

Uso:
    python add_novos_dados_images.py
"""
import random
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SOURCE_DIR = Path(r"C:\Users\24011603\Downloads\Novos dados\Radiographs")
DEST_DIR = Path("dados") / "images"
PREFIX = "nd_"

SPLIT_RATIOS = {"train": 0.760509, "valid": 0.084624, "test": 0.154867}
SPLIT_SEED = 42  # mesma semente usada em build_teeth_numbering_dataset.py


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
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Não encontrei {SOURCE_DIR}")

    files = sorted(SOURCE_DIR.iterdir())
    splits = assign_splits([p.name for p in files])

    contagem = {"train": 0, "valid": 0, "test": 0}
    pulados = 0

    for src in files:
        split = splits[src.name]
        dest = DEST_DIR / split / f"{PREFIX}{src.stem}.jpg"
        if dest.exists():
            pulados += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        contagem[split] += 1

    print("Imagens copiadas para dados/images/:")
    for split, n in contagem.items():
        print(f"  {split}: {n}")
    if pulados:
        print(f"{pulados} já existiam com esse nome e foram puladas (rode de novo com --force se precisar).")
    print(f"\nTotal: {sum(contagem.values())} imagens novas. Rode `python label_tool.py` para classificá-las.")


if __name__ == "__main__":
    main()
