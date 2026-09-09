import hashlib

# Mapeamento provisório dos 14 códigos de classe do dataset de treino
# (dados/data.yaml). Ainda não há confirmação oficial do significado de
# cada sigla — revise antes de usar em laudo real.
CLASS_LABELS = {
    "IMP": "Implante",
    "PRR": "Prótese Parcial Removível",
    "OBT": "Obturação",
    "END": "Tratamento Endodôntico",
    "CAR": "Cárie",
    "BON": "Perda Óssea",
    "IMT": "Dente Incluso/Impactado",
    "API": "Lesão Periapical",
    "ROT": "Raiz Residual",
    "FUR": "Lesão de Furca",
    "APS": "Ápice Aberto",
    "ROR": "Reabsorção Radicular",
    "ORD": "Aparelho Ortodôntico",
    "SRD": "Dente Supranumerário"
}

QUALITY_CATEGORIES = [
    ("positioning", "Posicionamento"),
    ("contrast", "Contraste"),
    ("sharpness", "Nitidez"),
    ("coverage", "Cobertura anatômica"),
    ("artifacts", "Artefatos")
]


def _seed_from_bytes(image_bytes: bytes) -> int:
    return int(hashlib.sha256(image_bytes).hexdigest(), 16)


def run_yolo_detection(image_bytes: bytes) -> dict:
    """
    Placeholder para o modelo YOLOv8 treinado nas 14 classes de
    dados/data.yaml. O repositório ainda só contém o checkpoint base
    (yolov8m.pt, pesos COCO) — nenhum treino foi salvo em
    runs/detect/.../weights/best.pt. Troque esta função por inferência
    real assim que houver um modelo treinado.
    """
    seed = _seed_from_bytes(image_bytes)
    codes = list(CLASS_LABELS.keys())
    picked_codes = list(dict.fromkeys([
        codes[seed % len(codes)],
        codes[(seed // 7) % len(codes)]
    ]))

    findings = []
    for i, code in enumerate(picked_codes):
        offset = (seed >> (i * 4)) % 100
        findings.append({
            "class_code": code,
            "label": CLASS_LABELS[code],
            "confidence": round(0.62 + (offset % 35) / 100, 2),
            "bbox": {
                "x": round(0.1 + (offset % 40) / 100, 3),
                "y": round(0.15 + (offset % 30) / 100, 3),
                "width": round(0.12 + (offset % 10) / 100, 3),
                "height": round(0.1 + (offset % 8) / 100, 3)
            }
        })

    return {
        "model": "yolov8-dental-14c",
        "findings": findings
    }


def run_efficientnet_adequacy(image_bytes: bytes) -> dict:
    """
    Placeholder para o classificador EfficientNet de adequação técnica
    (train_efficientnet.py). Nenhum checkpoint treinado foi encontrado no
    repositório — troque por inferência real quando houver um modelo salvo.
    """
    seed = _seed_from_bytes(image_bytes)
    score = 55 + (seed % 45)
    is_adequate = score >= 70

    criteria = []
    for i, (key, label) in enumerate(QUALITY_CATEGORIES):
        criterion_score = max(30, min(99, score + ((seed >> (i * 3)) % 21) - 10))
        criteria.append({
            "category": key,
            "label": label,
            "score": criterion_score,
            "status": (
                "approved" if criterion_score >= 75
                else "attention" if criterion_score >= 55
                else "rejected"
            )
        })

    return {
        "model": "efficientnet-b0-quality",
        "is_adequate": is_adequate,
        "score": score,
        "criteria": criteria,
        "recommendation": (
            "Exame com qualidade técnica adequada para diagnóstico."
            if is_adequate else
            "Qualidade técnica abaixo do ideal — considere repetir a captura antes do laudo."
        )
    }


def analyze_radiograph(image_bytes: bytes) -> dict:
    return {
        "yolo": run_yolo_detection(image_bytes),
        "efficientnet": run_efficientnet_adequacy(image_bytes)
    }
