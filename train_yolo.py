# train_yolo.py
"""
Treinamento do YOLOv8 para detecção dos 14 achados odontológicos de
dados/data.yaml (implante, cárie, lesão periapical, tratamento
endodôntico etc.).

Uso:
    python train_yolo.py                                  # configuração padrão (GPU se disponível)
    python train_yolo.py --device cpu --batch 2 --workers 0
    python train_yolo.py --model yolov8s.pt --epochs 150
    python train_yolo.py --check                          # só valida o dataset, não treina
    python train_yolo.py --resume runs/yolo/<run>/weights/last.pt
    python train_yolo.py --export                         # exporta para ONNX ao final

Dependências: ultralytics, torch, torchvision, pyyaml
    pip install ultralytics torch torchvision pyyaml
"""
import argparse
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def check_dependencies() -> None:
    required = {"ultralytics": "ultralytics", "torch": "torch torchvision", "yaml": "pyyaml"}
    missing = [pip_name for module, pip_name in required.items() if not _is_importable(module)]
    if missing:
        print("Dependências faltando. Instale com:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)


def _is_importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


check_dependencies()

import torch
import yaml
from ultralytics import YOLO

DEFAULT_DATA_YAML = "dados/data.yaml"
DEFAULT_MODEL = "yolov8m.pt"
DEFAULT_PROJECT = "runs/yolo"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# Augmentação ajustada para radiografias panorâmicas: sem flip vertical (perde
# orientação anatômica), rotação/translação/escala leves (variação realista
# de posicionamento do paciente), sem copy_paste (não faz sentido colar
# recortes de uma radiografia em outra).
AUGMENTATION = {
    "hsv_h": 0.015,
    "hsv_s": 0.2,
    "hsv_v": 0.4,
    "degrees": 5.0,
    "translate": 0.1,
    "scale": 0.3,
    "shear": 2.0,
    "perspective": 0.0001,
    "flipud": 0.0,
    "fliplr": 0.3,
    "mosaic": 0.5,
    "mixup": 0.1,
    "copy_paste": 0.0,
}


def setup_logging(output_dir: Path) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("RadIA.YOLO")


def detect_device(preferred: str, logger: logging.Logger) -> str:
    """Resolve o device a usar. `preferred="auto"` detecta automaticamente;
    qualquer outro valor (ex.: "cpu", "0", "mps") é usado como está."""
    if preferred != "auto":
        logger.info(f"Device forçado via --device: {preferred}")
        return preferred

    if torch.cuda.is_available():
        name = torch.cuda.get_device_properties(0).name
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"GPU detectada: {name} ({vram:.1f} GB VRAM) — usando device=0")
        return "0"

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        logger.info("Apple Silicon (MPS) detectado — usando device=mps")
        return "mps"

    logger.warning("Nenhuma GPU disponível — treinando em CPU (será mais lento)")
    return "cpu"


def ensure_portable_data_yaml(data_yaml: Path, logger: logging.Logger) -> None:
    """Corrige o campo `path` do data.yaml para apontar para esta máquina.

    O `path` é gerado como caminho absoluto (para o Ultralytics resolver
    train/val/test sem ambiguidade), mas isso quebra ao clonar o repo em
    outra máquina ou usuário. Reescreve sempre que necessário.
    """
    if not data_yaml.exists():
        logger.error(f"data.yaml não encontrado: {data_yaml}")
        sys.exit(1)

    with open(data_yaml, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    correct_path = str(data_yaml.parent.resolve())
    if cfg.get("path") != correct_path:
        logger.info(f"Corrigindo 'path' do data.yaml para esta máquina: {correct_path}")
        cfg["path"] = correct_path
        with open(data_yaml, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def validate_dataset(data_yaml: Path, logger: logging.Logger) -> dict:
    """Verifica integridade do dataset antes de treinar. Aborta (sys.exit)
    se algum split obrigatório estiver vazio ou algum label referenciar uma
    classe fora do intervalo declarado em `nc`."""
    logger.info("=" * 60)
    logger.info("Validando dataset")
    logger.info("=" * 60)

    with open(data_yaml, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    names = cfg.get("names", [])
    nc = cfg.get("nc", len(names))
    logger.info(f"Classes ({nc}): {names}")

    base = data_yaml.parent
    stats = {}

    for split in ["train", "valid", "test"]:
        img_dir = base / "images" / split
        lbl_dir = base / "labels" / split

        if not img_dir.exists():
            logger.warning(f"[{split}] pasta de imagens não encontrada: {img_dir}")
            continue

        images = [f for f in img_dir.glob("*") if f.suffix.lower() in IMAGE_EXTENSIONS]
        labels = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []

        image_stems = {f.stem for f in images}
        label_stems = {f.stem for f in labels}
        missing_labels = image_stems - label_stems
        orphan_labels = label_stems - image_stems

        class_counts: dict[int, int] = {}
        invalid_class_refs = 0
        for label_file in labels:
            for line in label_file.read_text().strip().splitlines():
                if not line.strip():
                    continue
                class_id = int(line.split()[0])
                if class_id >= nc:
                    invalid_class_refs += 1
                    continue
                class_counts[class_id] = class_counts.get(class_id, 0) + 1

        stats[split] = {
            "images": len(images),
            "labels": len(labels),
            "missing_labels": len(missing_labels),
            "orphan_labels": len(orphan_labels),
            "classes": class_counts,
        }

        logger.info(f"[{split.upper()}] imagens={len(images)} labels={len(labels)}")
        if missing_labels:
            logger.warning(f"  {len(missing_labels)} imagens sem label correspondente")
        if orphan_labels:
            logger.warning(f"  {len(orphan_labels)} labels sem imagem correspondente")
        if invalid_class_refs:
            logger.error(f"  {invalid_class_refs} anotações referenciam classe >= nc ({nc}) — corrija o dataset")
        for class_id, count in sorted(class_counts.items()):
            class_name = names[class_id] if class_id < len(names) else str(class_id)
            logger.info(f"  classe {class_id} ({class_name}): {count} anotações")

    if stats.get("train", {}).get("images", 0) == 0:
        logger.error("Nenhuma imagem de treino encontrada — abortando.")
        sys.exit(1)

    train_classes = stats["train"]["classes"]
    if train_classes:
        ratio = max(train_classes.values()) / max(min(train_classes.values()), 1)
        if ratio > 5:
            logger.warning(
                f"Dataset desbalanceado no treino (razão {ratio:.1f}x entre classe mais e menos frequente). "
                "Considere focar a avaliação em mAP por classe, não só no mAP médio."
            )

    logger.info("")
    return stats


def resolve_batch_and_amp(args: argparse.Namespace, device: str, logger: logging.Logger) -> tuple[int, bool]:
    batch = args.batch
    if batch == -1 and device == "cpu":
        logger.warning("Batch automático (-1) não é suportado em CPU — usando batch=8")
        batch = 8

    amp = args.amp if args.amp is not None else (device != "cpu")
    if device == "cpu" and amp:
        logger.warning("Mixed precision (amp) não traz benefício em CPU — desativando")
        amp = False

    return batch, amp


def train_model(args: argparse.Namespace, device: str, logger: logging.Logger) -> tuple[YOLO, object, str]:
    batch, amp = resolve_batch_and_amp(args, device, logger)
    run_name = args.name or f"radia_yolo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info("=" * 60)
    logger.info("Iniciando treinamento YOLOv8")
    logger.info("=" * 60)
    logger.info(f"modelo={args.model} epochs={args.epochs} batch={batch} imgsz={args.imgsz} device={device}")
    logger.info(f"workers={args.workers} amp={amp} patience={args.patience}")

    if args.resume:
        logger.info(f"Retomando treino a partir de: {args.resume}")
        model = YOLO(args.resume)
        t0 = time.time()
        model.train(resume=True)
        logger.info(f"Treinamento concluído em {(time.time() - t0) / 60:.1f} min")
        return model, None, Path(args.resume).parent.parent.name

    model = YOLO(args.model)
    t0 = time.time()

    results = model.train(
        data=str(args.data),
        epochs=args.epochs,
        patience=args.patience,
        batch=batch,
        imgsz=args.imgsz,
        device=device,
        project=args.project,
        name=run_name,
        exist_ok=True,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        workers=args.workers,
        amp=amp,
        seed=args.seed,
        conf=0.25,
        iou=0.7,
        verbose=True,
        plots=True,
        save=True,
        save_period=10,
        val=True,
        **AUGMENTATION,
    )

    logger.info(f"Treinamento concluído em {(time.time() - t0) / 60:.1f} min")
    return model, results, run_name


def evaluate_model(model: YOLO, args: argparse.Namespace, device: str, logger: logging.Logger) -> object:
    logger.info("=" * 60)
    logger.info("Avaliação no conjunto de teste")
    logger.info("=" * 60)

    test_dir = args.data.parent / "images" / "test"
    if not test_dir.exists() or not any(test_dir.iterdir()):
        logger.warning("Conjunto de teste vazio ou não encontrado — pulando avaliação.")
        return None

    metrics = model.val(data=str(args.data), split="test", device=device, conf=0.25, iou=0.7, plots=True, verbose=True)

    logger.info("Métricas no conjunto de teste:")
    logger.info(f"  mAP50    : {metrics.box.map50:.4f}")
    logger.info(f"  mAP50-95 : {metrics.box.map:.4f}")
    logger.info(f"  Precisão : {metrics.box.mp:.4f}")
    logger.info(f"  Recall   : {metrics.box.mr:.4f}")
    return metrics


def export_model(model: YOLO, output_dir: Path, run_name: str, logger: logging.Logger) -> None:
    logger.info("=" * 60)
    logger.info("Exportando modelo para ONNX")
    logger.info("=" * 60)

    try:
        onnx_path = model.export(format="onnx", dynamic=True, simplify=True)
        logger.info(f"ONNX exportado: {onnx_path}")
    except Exception as e:
        logger.warning(f"Exportação ONNX falhou: {e}")

    best_src = output_dir / run_name / "weights" / "best.pt"
    if best_src.exists():
        dest = output_dir / "radia_yolo_best.pt"
        shutil.copy(best_src, dest)
        logger.info(f"Melhor checkpoint copiado para: {dest}")


def print_summary(output_dir: Path, run_name: str, logger: logging.Logger) -> None:
    logger.info("=" * 60)
    logger.info("Concluído — arquivos gerados")
    logger.info("=" * 60)

    run_dir = output_dir / run_name
    artifacts = [
        ("Melhor modelo", run_dir / "weights" / "best.pt"),
        ("Último checkpoint", run_dir / "weights" / "last.pt"),
        ("Curvas de treino", run_dir / "results.png"),
        ("Matriz de confusão", run_dir / "confusion_matrix.png"),
        ("Curva PR", run_dir / "PR_curve.png"),
        ("Curva F1", run_dir / "F1_curve.png"),
        ("Log CSV", run_dir / "results.csv"),
    ]
    for label, path in artifacts:
        status = "OK" if path.exists() else "--"
        logger.info(f"  [{status}] {label:20s} {path}")

    logger.info("")
    logger.info("Próximos passos:")
    logger.info("  1. Confira results.png e confusion_matrix.png")
    logger.info("  2. Se o mAP50-95 estiver baixo, considere mais épocas, mais dados ou um modelo maior")
    logger.info(f"  3. Use {run_dir / 'weights' / 'best.pt'} em app/services/analysis_service.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path(DEFAULT_DATA_YAML), help="Caminho do data.yaml")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Peso base do YOLOv8 (n/s/m/l/x)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=20, help="Early stopping: épocas sem melhora")
    parser.add_argument("--batch", type=int, default=-1, help="-1 = automático (só em GPU)")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="auto", help="auto | cpu | 0 | 0,1 | mps")
    parser.add_argument("--workers", type=int, default=0 if sys.platform == "win32" else 8)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=None, help="Mixed precision (padrão: ligado fora de CPU)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--name", default=None, help="Nome da run (padrão: timestamp)")
    parser.add_argument("--resume", default=None, help="Caminho para last.pt de uma run interrompida")
    parser.add_argument("--export", action="store_true", help="Exportar para ONNX ao final do treino")
    parser.add_argument("--check", action="store_true", help="Só valida dataset e device, não treina")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # O Ultralytics injeta um prefixo "<runs_dir>/<task>/" na frente de
    # qualquer `project` relativo (ver ultralytics.cfg.get_save_dir) — sem
    # isso, os arquivos acabam em runs/detect/<project>/<name> em vez de
    # <project>/<name>, e evaluate_model/export_model/print_summary
    # procurariam no lugar errado.
    args.project = str(Path(args.project).resolve())

    print("=" * 60)
    print("RadIA QC — Treinamento YOLOv8")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    output_dir = Path(args.project)
    logger = setup_logging(output_dir)

    device = detect_device(args.device, logger)
    ensure_portable_data_yaml(args.data, logger)
    validate_dataset(args.data, logger)

    if args.check:
        logger.info("--check: dataset e device validados, encerrando sem treinar.")
        return

    model, _, run_name = train_model(args, device, logger)
    evaluate_model(model, args, device, logger)

    if args.export:
        export_model(model, output_dir, run_name, logger)

    print_summary(output_dir, run_name, logger)


if __name__ == "__main__":
    main()
