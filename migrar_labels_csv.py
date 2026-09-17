# migrar_labels_csv.py
"""
Migra dados/labels_qualidade.csv de caminhos absolutos (ex.:
"C:\\Users\\<usuario>\\teste1\\dados\\images\\train\\593.jpg") para o formato
relativo a DATA_DIR (ex.: "images/train/593.jpg"), que é o que label_tool.py
passou a usar em image_key() a partir de 15/09/2026.

Sem essa migração, ao rodar label_tool.py de novo (para rotular imagens
novas), a ferramenta não reconhece nenhuma das linhas já salvas — porque a
chave em memória (relativa) nunca bate com a chave salva no CSV (absoluta,
com o nome de usuário do Windows embutido) — e volta a pedir rótulo para
todas as imagens já classificadas.

Uso:
    python migrar_labels_csv.py
"""
import csv
import re
import sys
from pathlib import Path

from config import DATA_DIR

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

LABELS_CSV = DATA_DIR / "labels_qualidade.csv"


def to_relative_key(image_path: str) -> str:
    """Extrai "images/<split>/<arquivo>" de um caminho absoluto ou relativo."""
    normalized = image_path.replace("\\", "/")
    match = re.search(r"(images/[^/]+/[^/]+)$", normalized)
    return match.group(1) if match else normalized


def main() -> None:
    if not LABELS_CSV.exists():
        print(f"Não encontrei {LABELS_CSV}")
        return

    with open(LABELS_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    migrated, unchanged, colisoes = 0, 0, []
    seen = {}
    for row in rows:
        old = row["image_path"]
        new = to_relative_key(old)
        if new != old:
            migrated += 1
        else:
            unchanged += 1
        if new in seen and seen[new]["label"] != row["label"]:
            colisoes.append((new, seen[new]["label"], row["label"]))
        row["image_path"] = new
        seen[new] = row  # última ocorrência vence em caso de duplicata

    final_rows = list(seen.values())

    with open(LABELS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "split", "label"])
        writer.writeheader()
        for row in final_rows:
            writer.writerow(row)

    print(f"{migrated} caminhos convertidos para formato relativo, {unchanged} já estavam ok.")
    print(f"{len(rows) - len(final_rows)} linhas duplicadas removidas (mesma imagem rotulada 2x).")
    if colisoes:
        print(f"\nATENÇÃO: {len(colisoes)} imagens tiveram rótulos DIFERENTES em duplicatas "
              f"(ficou valendo o último rótulo do arquivo original):")
        for key, antigo, novo in colisoes:
            print(f"  {key}: {antigo} -> {novo}")
    print(f"\nTotal final: {len(final_rows)} imagens rotuladas em {LABELS_CSV}")


if __name__ == "__main__":
    main()
