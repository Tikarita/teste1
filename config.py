# config.py
from pathlib import Path

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "dados"

# Configurações YOLOv8
YOLO_CONFIG = {
    "data_yaml": str(DATA_DIR / "panoramic_qc.yaml"),
    "model_name": "yolov8m.pt",
    "imgsz": 960,
    "epochs": 120,
    "batch": 8,
    "device": 0,
    "project": "runs_qc",
    "name": "yolov8_panorama_qc",
}

# Configurações EfficientNet
EFFICIENTNET_CONFIG = {
    "train_dir": str(DATA_DIR / "panoramicas" / "train"),
    "val_dir": str(DATA_DIR / "panoramicas" / "valid"),
    "test_dir": str(DATA_DIR / "panoramicas" / "test"),
    "img_size": 512,
    "batch_size": 16,
    "epochs": 25,
    "lr": 1e-4,
    "num_classes": 2,  # aceitável, inaceitável
}

# Classes YOLO (erros de qualidade)
YOLO_CLASSES = [
    "cone_cut",           # Corte na imagem
    "coluna_sobreposta",  # Coluna vertebral sobreposta
    "lingua_palato",      # Língua não posicionada
    "artefato_metal",     # Artefato metálico
    "fantasma",           # Imagem fantasma/ghost
    "movimento",          # Blur por movimento
]

# Classes de qualidade (EfficientNet)
QC_CLASSES = ["inaceitavel", "aceitavel"]