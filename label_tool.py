# label_tool.py
"""
Ferramenta manual para classificar radiografias em adequado/inadequado.

Percorre dados/images/{train,valid,test}, mostra uma imagem por vez e salva
sua decisão em dados/labels_qualidade.csv. É retomável: se você fechar e
abrir de novo, ele pula direto para as imagens que ainda faltam.

Atalhos:
    → ou A   adequado
    ← ou I   inadequado
    S        pular (não rotula, só passa pra próxima)
    Backspace  desfazer o último rótulo

Uso:
    python label_tool.py

Dependências: pillow (tkinter já vem com o Python padrão)
"""
import argparse
import csv
import random
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from config import DATA_DIR

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

LABELS_CSV = DATA_DIR / "labels_qualidade.csv"
SPLITS = ["train", "valid", "test"]
IMAGE_EXTENSIONS = ["*.jpg", "*.jpeg", "*.png"]
MAX_DISPLAY = (820, 820)


def _images_in(directory: Path) -> list:
    paths = []
    for pattern in IMAGE_EXTENSIONS:
        paths.extend(directory.glob(pattern))
    return sorted(paths)


def list_all_images(seed: int = 42, extra_dirs: list = None) -> list:
    items = []
    for split in SPLITS:
        for path in _images_in(DATA_DIR / "images" / split):
            items.append((split, path))

    for extra_dir in extra_dirs or []:
        extra_path = Path(extra_dir)
        for path in _images_in(extra_path):
            items.append((extra_path.name, path))

    random.Random(seed).shuffle(items)
    return items


def load_existing_labels() -> dict:
    labels = {}
    if LABELS_CSV.exists():
        with open(LABELS_CSV, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                labels[row["image_path"]] = row
    return labels


def save_labels(labels: dict) -> None:
    LABELS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "split", "label"])
        writer.writeheader()
        for row in labels.values():
            writer.writerow(row)


class LabelApp:
    def __init__(self, items: list, labels: dict):
        self.items = items
        self.labels = labels
        self.history = []
        self.photo = None
        self.index = self._next_unlabeled(0)

        self.root = tk.Tk()
        self.root.title("Classificar radiografias — adequado / inadequado")
        self.root.geometry("900x780")

        self.info_label = tk.Label(self.root, font=("Segoe UI", 11))
        self.info_label.pack(pady=(12, 0))

        self.image_label = tk.Label(self.root)
        self.image_label.pack(pady=12)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=8)

        tk.Button(
            btn_frame, text="✗ Inadequado (←)", bg="#f8d7da", fg="#842029",
            font=("Segoe UI", 12, "bold"), width=18, height=2,
            command=lambda: self.label_current("inadequado")
        ).grid(row=0, column=0, padx=10)

        tk.Button(
            btn_frame, text="Pular (S)", font=("Segoe UI", 10), width=10, height=2,
            command=self.skip_current
        ).grid(row=0, column=1, padx=10)

        tk.Button(
            btn_frame, text="✓ Adequado (→)", bg="#d1e7dd", fg="#0f5132",
            font=("Segoe UI", 12, "bold"), width=18, height=2,
            command=lambda: self.label_current("adequado")
        ).grid(row=0, column=2, padx=10)

        tk.Button(
            self.root, text="↶ Desfazer última (Backspace)", command=self.undo
        ).pack(pady=(4, 10))

        self.root.bind("<Right>", lambda e: self.label_current("adequado"))
        self.root.bind("a", lambda e: self.label_current("adequado"))
        self.root.bind("<Left>", lambda e: self.label_current("inadequado"))
        self.root.bind("i", lambda e: self.label_current("inadequado"))
        self.root.bind("s", lambda e: self.skip_current())
        self.root.bind("<BackSpace>", lambda e: self.undo())

        self.show_current()

    def _next_unlabeled(self, start: int) -> int:
        i = start
        while i < len(self.items) and str(self.items[i][1]) in self.labels:
            i += 1
        return i

    def show_current(self) -> None:
        total = len(self.items)
        done = len(self.labels)

        if self.index >= total:
            self.info_label.config(text=f"Tudo rotulado! {done}/{total} imagens.")
            self.image_label.config(image="", text="Concluído.")
            return

        split, path = self.items[self.index]
        image = Image.open(path).convert("RGB")
        image.thumbnail(MAX_DISPLAY)
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.photo)

        self.info_label.config(
            text=f"[{split}] {path.name}   —   {done}/{total} rotuladas   ({total - done} restantes)"
        )

    def label_current(self, label: str) -> None:
        if self.index >= len(self.items):
            return
        split, path = self.items[self.index]
        key = str(path)
        self.labels[key] = {"image_path": key, "split": split, "label": label}
        self.history.append(key)
        save_labels(self.labels)
        self.index = self._next_unlabeled(self.index + 1)
        self.show_current()

    def skip_current(self) -> None:
        self.index = self._next_unlabeled(self.index + 1)
        self.show_current()

    def undo(self) -> None:
        if not self.history:
            return
        last_key = self.history.pop()
        self.labels.pop(last_key, None)
        save_labels(self.labels)
        for i, (_, path) in enumerate(self.items):
            if str(path) == last_key:
                self.index = i
                break
        self.show_current()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42, help="Semente do embaralhamento (ordem de exibição)")
    parser.add_argument(
        "--extra-dir", action="append", default=[],
        help="Pasta adicional com imagens (.jpg/.jpeg/.png) para incluir na fila. Pode repetir a opção."
    )
    args = parser.parse_args()

    all_items = list_all_images(seed=args.seed, extra_dirs=args.extra_dir)
    existing_labels = load_existing_labels()

    print(f"{len(all_items)} imagens encontradas (dados/images/{{train,valid,test}}"
          f"{' + ' + ', '.join(args.extra_dir) if args.extra_dir else ''})")
    print(f"{len(existing_labels)} já rotuladas anteriormente em {LABELS_CSV}")

    LabelApp(all_items, existing_labels).run()
