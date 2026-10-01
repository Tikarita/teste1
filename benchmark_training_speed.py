# benchmark_training_speed.py
"""
Mede o tempo real de alguns passos de treino (forward+backward) do
EfficientNet e do YOLO nesta maquina (CPU), para estimar o tempo total de
treino por extrapolacao, em vez de chutar com base em benchmarks genericos.
"""
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

N_STEPS = 5


def bench_efficientnet():
    import torch
    from torch import nn, optim
    from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
    from config import EFFICIENTNET_CONFIG

    DEVICE = torch.device("cpu")
    cfg = EFFICIENTNET_CONFIG

    def build_model(num_classes):
        # weights=None so o download dos pesos ImageNet falha nesta rede (bloqueada) -
        # para medir velocidade, a arquitetura com peso aleatorio tem o mesmo custo de
        # forward/backward que a pretreinada, entao serve igual para o benchmark.
        model = efficientnet_b0(weights=None)
        for param in model.features.parameters():
            param.requires_grad = False
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model.to(DEVICE)

    model = build_model(cfg["num_classes"])
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.classifier.parameters(), lr=cfg["lr"])

    batch = torch.randn(cfg["batch_size"], 3, cfg["img_size"], cfg["img_size"]).to(DEVICE)
    labels = torch.randint(0, cfg["num_classes"], (cfg["batch_size"],)).to(DEVICE)

    # warmup
    optimizer.zero_grad()
    out = model(batch)
    loss = criterion(out, labels)
    loss.backward()
    optimizer.step()

    t0 = time.time()
    for _ in range(N_STEPS):
        optimizer.zero_grad()
        out = model(batch)
        loss = criterion(out, labels)
        loss.backward()
        optimizer.step()
    elapsed = time.time() - t0
    per_batch = elapsed / N_STEPS
    print(f"EfficientNet: {per_batch:.2f}s/batch (batch_size={cfg['batch_size']}, img_size={cfg['img_size']})")
    return per_batch, cfg["batch_size"]


def bench_yolo():
    from ultralytics import YOLO
    import torch

    model = YOLO("yolov8m.pt")
    pt_model = model.model
    pt_model.train()

    imgsz = 640
    batch_size = 2
    dummy = torch.randn(batch_size, 3, imgsz, imgsz)

    # warmup (so forward, backward real exige targets no formato do ultralytics -
    # aqui medimos so o custo do forward, que domina o tempo em CPU)
    with torch.no_grad():
        pt_model(dummy)

    t0 = time.time()
    for _ in range(N_STEPS):
        with torch.no_grad():
            pt_model(dummy)
    elapsed = time.time() - t0
    per_batch = elapsed / N_STEPS
    print(f"YOLOv8m (so forward): {per_batch:.2f}s/batch (batch_size={batch_size}, imgsz={imgsz})")
    print("  (treino real tambem tem backward + calculo de loss - estimar ~2-3x isso)")
    return per_batch, batch_size


if __name__ == "__main__":
    print("Medindo velocidade real nesta maquina (pode levar 1-2 min)...\n")
    ef_time, ef_batch = bench_efficientnet()
    print()
    yolo_time, yolo_batch = bench_yolo()
