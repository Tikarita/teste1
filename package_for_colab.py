# package_for_colab.py
"""
Empacota os dados em dois .zip prontos para subir no Google Drive e treinar
no Google Colab (GPU gratis, sem o bloqueio de rede desta maquina):

  colab_upload/efficientnet_dataset.zip  - dados/panoramicas/ (ImageFolder)
  colab_upload/yolo_dataset.zip          - so as imagens com rotulo YOLO de
                                            14 classes (dados/images + dados/labels
                                            + data.yaml), nao as ~3200 imagens
                                            que so tem rotulo de qualidade.

Uso:
    python package_for_colab.py
"""
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path("colab_upload")
YOLO_STAGE = OUT_DIR / "_yolo_stage"


def package_efficientnet():
    print("Empacotando dataset do EfficientNet (dados/panoramicas)...")
    if not (Path("dados") / "panoramicas").exists():
        print("  dados/panoramicas nao existe - rode `python dataset_qc.py` antes.")
        return
    OUT_DIR.mkdir(exist_ok=True)
    archive = shutil.make_archive(
        str(OUT_DIR / "efficientnet_dataset"), "zip", root_dir="dados", base_dir="panoramicas"
    )
    print(f"  OK: {archive} ({Path(archive).stat().st_size / 1e9:.2f} GB)")


def package_yolo():
    print("Empacotando dataset do YOLO (14 classes, so imagens com bbox)...")
    if YOLO_STAGE.exists():
        shutil.rmtree(YOLO_STAGE)

    n_copied = 0
    for split in ("train", "valid", "test"):
        label_dir = Path("dados") / "labels" / split
        image_dir = Path("dados") / "images" / split
        if not label_dir.exists():
            continue
        dest_img = YOLO_STAGE / "images" / split
        dest_lbl = YOLO_STAGE / "labels" / split
        dest_img.mkdir(parents=True, exist_ok=True)
        dest_lbl.mkdir(parents=True, exist_ok=True)

        for label_file in label_dir.glob("*.txt"):
            img_file = None
            for ext in (".jpg", ".jpeg", ".png"):
                candidate = image_dir / f"{label_file.stem}{ext}"
                if candidate.exists():
                    img_file = candidate
                    break
            if img_file is None:
                continue
            shutil.copy2(img_file, dest_img / img_file.name)
            shutil.copy2(label_file, dest_lbl / label_file.name)
            n_copied += 1

    shutil.copy2(Path("dados") / "data.yaml", YOLO_STAGE / "data.yaml")

    OUT_DIR.mkdir(exist_ok=True)
    archive = shutil.make_archive(str(OUT_DIR / "yolo_dataset"), "zip", root_dir=YOLO_STAGE)
    shutil.rmtree(YOLO_STAGE)
    print(f"  OK: {n_copied} imagens, {archive} ({Path(archive).stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    package_efficientnet()
    package_yolo()
    print(f"\nArquivos prontos em {OUT_DIR.resolve()}/ - suba os dois para o Google Drive.")
