import os
import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime

# ── Verificar dependências ──────────────────────────────────────────────────
def check_deps():
    missing = []
    try: import ultralytics
    except ImportError: missing.append("ultralytics")
    try: import torch
    except ImportError: missing.append("torch torchvision")
    try: import yaml
    except ImportError: missing.append("pyyaml")
    try:
        import psutil
    except ImportError:
        missing.append("psutil")
    if missing:
        print(f"\n[ERRO] Instale as dependências faltantes:")
        print(f"  pip install {' '.join(missing)}\n")
        sys.exit(1)

check_deps()

import yaml
import torch
from ultralytics import YOLO

# ══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO — EDITE AQUI
# ══════════════════════════════════════════════════════════════════

CONFIG = {
    # ── Dados ─────────────────────────────────────────────────────
    "data_yaml":   "dados/data.yaml",       # caminho do seu data.yaml
    "output_dir":  "runs/yolo",             # onde salvar os resultados

    # ── Modelo base ───────────────────────────────────────────────
    # Opções (do menor para o maior/mais preciso):
    # "yolov8n.pt"  → Nano    (~3MB)  — datasets pequenos / CPU
    # "yolov8s.pt"  → Small   (~11MB) — RECOMENDADO para início
    # "yolov8m.pt"  → Medium  (~26MB) — datasets maiores
    # "yolov8l.pt"  → Large   (~44MB) — se tiver GPU boa
    # "yolov8x.pt"  → XLarge  (~68MB) — máxima precisão
    "model":       "yolov8s.pt",

    # ── Hiperparâmetros ───────────────────────────────────────────
    "epochs":      100,          # épocas totais
    "patience":    20,           # early stopping (para se não melhorar)
    "batch":       -1,           # -1 = automático conforme VRAM/RAM
    "imgsz":       640,          # tamanho da imagem (múltiplo de 32)
    "lr0":         0.01,         # learning rate inicial
    "lrf":         0.01,         # learning rate final (fração do lr0)
    "momentum":    0.937,
    "weight_decay":0.0005,
    "warmup_epochs":3.0,

    # ── Augmentação ───────────────────────────────────────────────
    # (cruciais para dataset pequeno de radiografias)
    "hsv_h":       0.015,        # variação de matiz
    "hsv_s":       0.2,          # variação de saturação
    "hsv_v":       0.4,          # variação de brilho — simula sub/superexposição
    "degrees":     5.0,          # rotação leve — simula inclinação da cabeça
    "translate":   0.1,          # translação — simula deslocamento do sensor
    "scale":       0.3,          # escala — simula variação de zoom
    "shear":       2.0,          # cisalhamento
    "perspective": 0.0001,       # perspectiva
    "flipud":      0.0,          # flip vertical (NÃO usar em radiografias — perde orientação)
    "fliplr":      0.3,          # flip horizontal (CUIDADO: só se seu problema for simétrico)
    "mosaic":      0.5,          # mosaic augmentation
    "mixup":       0.1,          # mixup augmentation
    "copy_paste":  0.0,

    # ── Hardware ──────────────────────────────────────────────────
    "workers":     4,            # threads de carregamento de dados
    "amp":         True,         # mixed precision (mais rápido na GPU)
    "seed":        42,           # reprodutibilidade

    # ── Avaliação ─────────────────────────────────────────────────
    "conf":        0.25,         # threshold de confiança para métricas
    "iou":         0.7,          # threshold IoU para NMS

    # ── Exportação ────────────────────────────────────────────────
    "export_after_train": True,  # exportar para ONNX após treino
}

# ══════════════════════════════════════════════════════════════════
# LOGGING PROFISSIONAL
# ══════════════════════════════════════════════════════════════════

def setup_logging(output_dir: Path) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger("RadIA.YOLO")


# ══════════════════════════════════════════════════════════════════
# VALIDAÇÃO DO DATASET
# ══════════════════════════════════════════════════════════════════

def validar_dataset(data_yaml: Path, logger: logging.Logger) -> dict:
    """Verifica integridade do dataset antes de treinar."""

    logger.info("=" * 60)
    logger.info("  Validando dataset...")
    logger.info("=" * 60)

    if not data_yaml.exists():
        logger.error(f"data.yaml não encontrado: {data_yaml}")
        sys.exit(1)

    with open(data_yaml) as f:
        cfg = yaml.safe_load(f)

    logger.info(f"Classes : {cfg.get('names', [])}")
    logger.info(f"N° classes: {cfg.get('nc', '?')}")

    base = data_yaml.parent
    stats = {}

    for split in ["train", "valid", "test"]:
        img_dir = base / "images" / split
        lbl_dir = base / "labels" / split

        if not img_dir.exists():
            logger.warning(f"  Pasta não encontrada: {img_dir}")
            continue

        imgs = list(img_dir.glob("*"))
        imgs = [f for f in imgs if f.suffix.lower() in
                {".jpg",".jpeg",".png",".bmp",".tiff",".tif",".webp"}]
        lbls = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []

        # Verificar correspondência imagem ↔ label
        img_stems = {f.stem for f in imgs}
        lbl_stems = {f.stem for f in lbls}
        sem_label  = img_stems - lbl_stems
        sem_imagem = lbl_stems - img_stems

        # Contar classes nos labels
        class_counts = {}
        for lbl in lbls:
            for line in lbl.read_text().strip().splitlines():
                if line.strip():
                    cls = int(line.split()[0])
                    class_counts[cls] = class_counts.get(cls, 0) + 1

        stats[split] = {
            "imagens": len(imgs),
            "labels":  len(lbls),
            "sem_label":  len(sem_label),
            "sem_imagem": len(sem_imagem),
            "classes": class_counts,
        }

        logger.info(f"\n  [{split.upper()}]")
        logger.info(f"    Imagens     : {len(imgs)}")
        logger.info(f"    Labels      : {len(lbls)}")
        if sem_label:
            logger.warning(f"    Sem label   : {len(sem_label)} arquivos")
        if sem_imagem:
            logger.warning(f"    Sem imagem  : {len(sem_imagem)} labels órfãos")
        for cls_id, n in sorted(class_counts.items()):
            nome = cfg.get("names", {})
            nome_cls = nome[cls_id] if isinstance(nome, list) and cls_id < len(nome) else str(cls_id)
            logger.info(f"    Classe {cls_id} ({nome_cls}): {n} anotações")

    # Verificar desbalanceamento
    if "train" in stats:
        classes = stats["train"].get("classes", {})
        if classes:
            max_c = max(classes.values())
            min_c = min(classes.values())
            ratio = max_c / max(min_c, 1)
            if ratio > 5:
                logger.warning(
                    f"\n  [ATENÇÃO] Dataset DESBALANCEADO — ratio {ratio:.1f}x"
                    f"\n  Considere: class_weights ou oversampling da classe minoritária"
                )

    logger.info("")
    return stats


# ══════════════════════════════════════════════════════════════════
# GERAR / CORRIGIR data.yaml
# ══════════════════════════════════════════════════════════════════

def gerar_data_yaml(data_path: Path, logger: logging.Logger):
    """Gera ou valida o data.yaml com caminhos absolutos."""

    yaml_path = data_path / "data.yaml"

    if yaml_path.exists():
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f)

        # Garantir caminho absoluto
        cfg["path"] = str(data_path.resolve())
        if "train" not in cfg:
            cfg["train"] = "images/train"
        if "val" not in cfg:
            cfg["val"] = "images/valid"
        if "test" not in cfg:
            cfg["test"] = "images/test"

        with open(yaml_path, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"data.yaml atualizado com caminho absoluto: {data_path.resolve()}")
    else:
        # Detectar classes pelas pastas de labels
        lbl_train = data_path / "labels" / "train"
        classes_detectadas = set()
        if lbl_train.exists():
            for lbl in lbl_train.glob("*.txt"):
                for line in lbl.read_text().strip().splitlines():
                    if line.strip():
                        classes_detectadas.add(int(line.split()[0]))

        nc = max(classes_detectadas) + 1 if classes_detectadas else 2
        nomes = {0: "correto", 1: "defeituoso"}
        names_list = [nomes.get(i, f"classe_{i}") for i in range(nc)]

        cfg = {
            "path":  str(data_path.resolve()),
            "train": "images/train",
            "val":   "images/valid",
            "test":  "images/test",
            "nc":    nc,
            "names": names_list,
        }
        with open(yaml_path, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"data.yaml gerado automaticamente: {nc} classes → {names_list}")

    return yaml_path


# ══════════════════════════════════════════════════════════════════
# INFORMAÇÕES DE HARDWARE
# ══════════════════════════════════════════════════════════════════

def log_hardware(logger: logging.Logger):
    import psutil
    logger.info("\n" + "=" * 60)
    logger.info("  Hardware")
    logger.info("=" * 60)

    if torch.cuda.is_available():
        n_gpus = torch.cuda.device_count()
        logger.info(f"  GPU disponível : SIM ({n_gpus}x)")
        for i in range(n_gpus):
            props = torch.cuda.get_device_properties(i)
            vram  = props.total_memory / 1024**3
            logger.info(f"    GPU {i}: {props.name} — {vram:.1f} GB VRAM")
        device = "0"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        logger.info("  Apple Silicon (MPS): disponível")
        device = "mps"
    else:
        logger.info("  GPU: NÃO disponível — treinando em CPU (lento!)")
        logger.warning("  Considere Google Colab (GPU gratuita) para acelerar")
        device = "cpu"

    cpu_count = os.cpu_count()
    logger.info(f"  CPUs           : {cpu_count}")

    import psutil
    ram_gb = psutil.virtual_memory().total / 1024**3
    logger.info(f"  RAM total      : {ram_gb:.1f} GB")

    logger.info("")
    return device


# ══════════════════════════════════════════════════════════════════
# TREINAMENTO
# ══════════════════════════════════════════════════════════════════

def treinar(cfg: dict, logger: logging.Logger):
    logger.info("\n" + "=" * 60)
    logger.info("  Iniciando Treinamento YOLOv8")
    logger.info("=" * 60)
    logger.info(f"  Modelo base : {cfg['model']}")
    logger.info(f"  Épocas      : {cfg['epochs']}")
    logger.info(f"  Batch       : {cfg['batch']} (automático se -1)")
    logger.info(f"  Imagem      : {cfg['imgsz']}px")
    logger.info(f"  Early stop  : {cfg['patience']} épocas sem melhora")
    logger.info("")

    # Instanciar modelo
    model = YOLO(cfg["model"])

    # Parâmetros de treino
    run_name = f"radia_yolo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    t0 = time.time()

    results = model.train(
        data        = cfg["data_yaml"],
        epochs      = cfg["epochs"],
        patience    = cfg["patience"],
        batch       = cfg["batch"],
        imgsz       = cfg["imgsz"],
        project     = cfg["output_dir"],
        name        = run_name,
        exist_ok    = True,
        pretrained  = True,
        optimizer   = "AdamW",   # melhor para datasets médicos pequenos
        lr0         = cfg["lr0"],
        lrf         = cfg["lrf"],
        momentum    = cfg["momentum"],
        weight_decay= cfg["weight_decay"],
        warmup_epochs=cfg["warmup_epochs"],
        # Augmentação médica
        hsv_h       = cfg["hsv_h"],
        hsv_s       = cfg["hsv_s"],
        hsv_v       = cfg["hsv_v"],
        degrees     = cfg["degrees"],
        translate   = cfg["translate"],
        scale       = cfg["scale"],
        shear       = cfg["shear"],
        perspective = cfg["perspective"],
        flipud      = cfg["flipud"],
        fliplr      = cfg["fliplr"],
        mosaic      = cfg["mosaic"],
        mixup       = cfg["mixup"],
        copy_paste  = cfg["copy_paste"],
        # Hardware
        workers     = cfg["workers"],
        amp         = cfg["amp"],
        seed        = cfg["seed"],
        # Avaliação
        conf        = cfg["conf"],
        iou         = cfg["iou"],
        # Logs
        verbose     = True,
        plots       = True,
        save        = True,
        save_period = 10,   # salva checkpoint a cada 10 épocas
        val         = True,
    )

    t_total = time.time() - t0
    logger.info(f"\n  Treinamento concluído em {t_total/60:.1f} minutos")

    return model, results, run_name


# ══════════════════════════════════════════════════════════════════
# AVALIAÇÃO
# ══════════════════════════════════════════════════════════════════

def avaliar(model, cfg: dict, run_name: str, logger: logging.Logger):
    logger.info("\n" + "=" * 60)
    logger.info("  Avaliação no conjunto de TESTE")
    logger.info("=" * 60)

    data_path = Path(cfg["data_yaml"]).parent
    test_dir  = data_path / "images" / "test"

    if not test_dir.exists() or not any(test_dir.iterdir()):
        logger.warning("  Conjunto test vazio ou não encontrado. Pulando avaliação no test.")
        return

    metrics = model.val(
        data    = cfg["data_yaml"],
        split   = "test",
        conf    = cfg["conf"],
        iou     = cfg["iou"],
        plots   = True,
        verbose = True,
    )

    logger.info("\n  Métricas no conjunto de teste:")
    try:
        logger.info(f"    mAP50      : {metrics.box.map50:.4f}")
        logger.info(f"    mAP50-95   : {metrics.box.map:.4f}")
        logger.info(f"    Precisão   : {metrics.box.mp:.4f}")
        logger.info(f"    Recall     : {metrics.box.mr:.4f}")
    except Exception:
        try:
            logger.info(f"    Top-1 Acc  : {metrics.top1:.4f}")
            logger.info(f"    Top-5 Acc  : {metrics.top5:.4f}")
        except Exception:
            logger.info("  (métricas detalhadas disponíveis nos plots)")

    return metrics


# ══════════════════════════════════════════════════════════════════
# EXPORTAÇÃO
# ══════════════════════════════════════════════════════════════════

def exportar(model, output_dir: Path, run_name: str, logger: logging.Logger):
    logger.info("\n" + "=" * 60)
    logger.info("  Exportando modelo para ONNX")
    logger.info("=" * 60)

    try:
        onnx_path = model.export(format="onnx", dynamic=True, simplify=True)
        logger.info(f"  ONNX exportado: {onnx_path}")
    except Exception as e:
        logger.warning(f"  Exportação ONNX falhou: {e}")

    # Copiar best.pt para pasta raiz
    best_src = output_dir / run_name / "weights" / "best.pt"
    if best_src.exists():
        dest = output_dir / "radia_yolo_best.pt"
        shutil.copy(best_src, dest)
        logger.info(f"  Melhor modelo copiado: {dest}")


# ══════════════════════════════════════════════════════════════════
# RESUMO FINAL
# ══════════════════════════════════════════════════════════════════

def resumo_final(output_dir: Path, run_name: str, logger: logging.Logger):
    logger.info("\n" + "=" * 60)
    logger.info("  CONCLUÍDO — Resumo dos arquivos gerados")
    logger.info("=" * 60)

    run_dir = output_dir / run_name
    arquivos_importantes = [
        ("Melhor modelo",   run_dir / "weights" / "best.pt"),
        ("Último modelo",   run_dir / "weights" / "last.pt"),
        ("Curva de loss",   run_dir / "results.png"),
        ("Matriz confusão", run_dir / "confusion_matrix.png"),
        ("PR Curve",        run_dir / "PR_curve.png"),
        ("F1 Curve",        run_dir / "F1_curve.png"),
        ("Log de treino",   run_dir / "results.csv"),
    ]
    for nome, path in arquivos_importantes:
        status = "✓" if path.exists() else "✗"
        logger.info(f"  {status} {nome:20s}: {path}")

    logger.info("\n  Próximos passos:")
    logger.info("  1. Analise as curvas em results.png")
    logger.info("  2. Se mAP < 0.80 → aumente epochs ou adicione mais dados")
    logger.info("  3. Use best.pt no pipeline RadIA QC")
    logger.info(f"  4. Treine EfficientNet: python train_efficientnet.py")
    logger.info("")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("  RadIA QC — Treinamento YOLOv8")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    output_dir = Path(CONFIG["output_dir"])
    logger = setup_logging(output_dir)

    # Hardware
    device = log_hardware(logger)

    # Validar / gerar data.yaml
    data_path = Path(CONFIG["data_yaml"]).parent
    yaml_path = gerar_data_yaml(data_path, logger)
    CONFIG["data_yaml"] = str(yaml_path)

    # Validar dataset
    validar_dataset(yaml_path, logger)

    # Treinar
    model, results, run_name = treinar(CONFIG, logger)

    # Avaliar no test
    avaliar(model, CONFIG, run_name, logger)

    # Exportar
    if CONFIG["export_after_train"]:
        exportar(model, output_dir, run_name, logger)

    # Resumo
    resumo_final(output_dir, run_name, logger)


