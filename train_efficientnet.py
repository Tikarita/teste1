# train_efficientnet.py
"""
Treina um classificador binário (aceitável / inaceitável) para controle de
qualidade de radiografias panorâmicas, usando EfficientNet-B0 pré-treinada
na ImageNet (transfer learning).

Estrutura de dados esperada (ImageFolder), conforme EFFICIENTNET_CONFIG:

    dados/panoramicas/
    ├── train/
    │   ├── adequado/
    │   └── inadequado/
    ├── valid/
    │   ├── adequado/
    │   └── inadequado/
    └── test/
        ├── adequado/
        └── inadequado/

Essas pastas ainda não existem no repositório — gere os rótulos (ex.: com
dataset_qc.py) e organize as imagens em subpastas por classe antes de rodar.

Dependências: torch, torchvision, scikit-learn, pillow
    pip install torch torchvision scikit-learn pillow
"""
import copy
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import torch
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
from sklearn.metrics import classification_report, confusion_matrix

from config import EFFICIENTNET_CONFIG

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
OUTPUT_DIR = Path("runs_qc") / "efficientnet"
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transforms(img_size: int):
    train_tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.RandomRotation(degrees=5),
        transforms.ColorJitter(brightness=0.15, contrast=0.15),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return train_tf, eval_tf


def build_dataloaders(cfg: dict):
    train_tf, eval_tf = build_transforms(cfg["img_size"])

    train_ds = datasets.ImageFolder(cfg["train_dir"], transform=train_tf)
    val_ds = datasets.ImageFolder(cfg["val_dir"], transform=eval_tf)
    test_ds = datasets.ImageFolder(cfg["test_dir"], transform=eval_tf)

    if not (train_ds.classes == val_ds.classes == test_ds.classes):
        raise ValueError(
            "As subpastas de classe em train/valid/test precisam ser iguais e na "
            f"mesma ordem. Encontrado: train={train_ds.classes}, "
            f"valid={val_ds.classes}, test={test_ds.classes}"
        )
    if len(train_ds.classes) != cfg["num_classes"]:
        raise ValueError(
            f"num_classes={cfg['num_classes']} em EFFICIENTNET_CONFIG não bate com "
            f"as {len(train_ds.classes)} subpastas encontradas: {train_ds.classes}"
        )

    common = dict(batch_size=cfg["batch_size"], num_workers=4, pin_memory=True)
    train_loader = DataLoader(train_ds, shuffle=True, **common)
    val_loader = DataLoader(val_ds, shuffle=False, **common)
    test_loader = DataLoader(test_ds, shuffle=False, **common)

    return train_loader, val_loader, test_loader, train_ds.classes


def build_model(num_classes: int) -> nn.Module:
    model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)

    for param in model.features.parameters():
        param.requires_grad = False

    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model.to(DEVICE)


def build_feature_extractor() -> nn.Module:
    """
    EfficientNet-B0 pré-treinada na ImageNet, sem cabeça de classificação.
    Usada como extrator de embeddings (vetor de 1280 dimensões) quando ainda
    não há rótulos aceitável/inaceitável para treinar de verdade — ver
    baseline_efficientnet.py.
    """
    model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier = nn.Identity()
    model.eval()
    return model.to(DEVICE)


def run_epoch(model: nn.Module, loader: DataLoader, criterion, optimizer=None):
    is_train = optimizer is not None
    model.train() if is_train else model.eval()

    total_loss, total_correct, total_samples = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for images, labels in loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)

            if is_train:
                optimizer.zero_grad()

            outputs = model(images)
            loss = criterion(outputs, labels)

            if is_train:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * images.size(0)
            total_correct += (outputs.argmax(1) == labels).sum().item()
            total_samples += images.size(0)

    return total_loss / total_samples, total_correct / total_samples


def evaluate(model: nn.Module, loader: DataLoader, classes: list[str]) -> None:
    model.eval()
    all_preds, all_labels = [], []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(DEVICE)
            preds = model(images).argmax(1).cpu()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.tolist())

    print("\n=== Avaliação no conjunto de teste ===")
    print(classification_report(all_labels, all_preds, target_names=classes, digits=3))
    print("Matriz de confusão (linhas=real, colunas=previsto):")
    print(confusion_matrix(all_labels, all_preds))


def train(cfg: dict = None, patience: int = 7):
    cfg = cfg or EFFICIENTNET_CONFIG
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader, classes = build_dataloaders(cfg)
    print(f"Classes (ordem dos índices do modelo): {classes}")

    model = build_model(cfg["num_classes"])
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.classifier.parameters(), lr=cfg["lr"])
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=3)

    best_val_loss = float("inf")
    best_state = None
    epochs_sem_melhora = 0

    for epoch in range(1, cfg["epochs"] + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion)
        scheduler.step(val_loss)

        print(
            f"[{epoch:03d}/{cfg['epochs']}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            epochs_sem_melhora = 0
            torch.save(best_state, OUTPUT_DIR / "best.pt")
        else:
            epochs_sem_melhora += 1
            if epochs_sem_melhora >= patience:
                print(f"Sem melhora em {patience} épocas — parando (early stopping).")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    with open(OUTPUT_DIR / "classes.json", "w", encoding="utf-8") as f:
        json.dump(list(classes), f, ensure_ascii=False, indent=2)

    evaluate(model, test_loader, classes)
    return model, classes


def load_model(checkpoint_path: str, num_classes: int) -> nn.Module:
    model = build_model(num_classes)
    model.load_state_dict(torch.load(checkpoint_path, map_location=DEVICE))
    model.eval()
    return model


def predict_image(model: nn.Module, image_path: str, img_size: int, classes: list[str]) -> dict:
    """Classifica uma única radiografia como aceitável/inaceitável."""
    from PIL import Image

    _, eval_tf = build_transforms(img_size)
    image = Image.open(image_path).convert("RGB")
    tensor = eval_tf(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        probs = torch.softmax(model(tensor), dim=1)[0]
        pred_idx = int(probs.argmax())

    return {
        "label": classes[pred_idx],
        "confidence": round(float(probs[pred_idx]), 4),
        "probabilities": {c: round(float(p), 4) for c, p in zip(classes, probs)},
    }


if __name__ == "__main__":
    print(f"Usando dispositivo: {DEVICE}")
    train()
