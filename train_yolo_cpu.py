# train_yolo_cpu.py
from ultralytics import YOLO
import os
from pathlib import Path

# Configurações
DATASET_DIR = "dados"
DATA_YAML = f"{DATASET_DIR}/data.yaml"
MODEL_NAME = "yolov8m.pt"
EPOCHS = 50      # ⚠️ Reduzido para CPU
BATCH = 2        # ⚠️ Reduzido para CPU
IMGSZ = 640
WORKERS = 0      # ⚠️ 0 para Windows

def verificar_dataset():
    """Verifica se o dataset está correto antes de treinar."""
    print("🔍 Verificando dataset...")
    
    yaml_path = Path(DATA_YAML)
    if not yaml_path.exists():
        print(f"❌ YAML não encontrado: {DATA_YAML}")
        return False
    
    # Lê o YAML
    import yaml
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"✅ YAML encontrado: {DATA_YAML}")
    print(f"   Path: {config.get('path', 'N/A')}")
    print(f"   Train: {config.get('train')}")
    print(f"   Val: {config.get('val')}")
    print(f"   Classes: {config.get('nc')}")
    
    # Verifica pastas
    base_path = Path(DATASET_DIR)
    train_imgs = base_path / "images" / "train"
    val_imgs = base_path / "images" / "valid"
    test_imgs = base_path / "images" / "test"
    
    train_labels = base_path / "labels" / "train"
    val_labels = base_path / "labels" / "valid"
    
    if train_imgs.exists():
        n_train = len(list(train_imgs.glob("*.jpg"))) + len(list(train_imgs.glob("*.png")))
        print(f"   📁 Imagens train: {n_train}")
    else:
        print(f"   ❌ Pasta train não encontrada: {train_imgs}")
    
    if val_imgs.exists():
        n_val = len(list(val_imgs.glob("*.jpg"))) + len(list(val_imgs.glob("*.png")))
        print(f"   📁 Imagens val: {n_val}")
    else:
        print(f"   ❌ Pasta val não encontrada: {val_imgs}")
    
    if test_imgs.exists():
        n_test = len(list(test_imgs.glob("*.jpg"))) + len(list(test_imgs.glob("*.png")))
        print(f"   📁 Imagens test: {n_test}")
    
    if train_labels.exists():
        n_labels = len(list(train_labels.glob("*.txt")))
        print(f"   📄 Labels train: {n_labels}")
    else:
        print(f"   ❌ Pasta labels train não encontrada: {train_labels}")
    
    return True

def train_yolo():
    """Treina YOLOv8 para CPU."""
    
    print("\n" + "="*60)
    print("🚀 INICIANDO TREINAMENTO YOLOv8 - CPU")
    print("="*60 + "\n")
    
    # Verifica dataset
    if not verificar_dataset():
        print("\n❌ Dataset inválido. Corrija antes de continuar.")
        return
    
    print("\n🔧 Carregando modelo...")
    model = YOLO(MODEL_NAME)
    print(f"✅ Modelo carregado: {MODEL_NAME}")
    
    print(f"\n📊 Configurações:")
    print(f"   Dataset: {DATASET_DIR}")
    print(f"   Data YAML: {DATA_YAML}")
    print(f"   Epochs: {EPOCHS}")
    print(f"   Batch: {BATCH}")
    print(f"   Image size: {IMGSZ}")
    print(f"   Workers: {WORKERS}")
    print(f"   Device: CPU ⚠️")
    
    print("\n⏳ Iniciando treinamento (pode demorar na CPU)...")
    print("-" * 60 + "\n")
    
    try:
        results = model.train(
            data=DATA_YAML,
            model=MODEL_NAME,
            epochs=EPOCHS,
            batch=BATCH,
            imgsz=IMGSZ,
            workers=WORKERS,
            device="cpu",  # ✅ FORÇA CPU
            verbose=True,
            exist_ok=True,
            project="runs_qc",
            name="yolov8_panorama_14classes_cpu",
            pretrained=True,
            optimizer="AdamW",
            lr0=0.001,
            patience=30,
            save=True,
            save_period=10,
            amp=False,  # ✅ Desativa mixed precision para CPU
        )
        
        print("\n" + "="*60)
        print("✅ TREINAMENTO CONCLUÍDO!")
        print("="*60)
        print(f"\n📁 Modelo salvo em: runs_qc/yolov8_panorama_14classes_cpu/weights/best.pt")
        
        # Validação
        print("\n🔍 Validação...")
        metrics = model.val(data=DATA_YAML)
        print(f"   mAP50: {metrics.box.map50:.4f}")
        print(f"   mAP50-95: {metrics.box.map:.4f}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ ERRO NO TREINAMENTO: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    train_yolo()