import hashlib
from io import BytesIO

import numpy as np
from PIL import Image

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
    ("sharpness", "Nitidez"),
    ("contrast", "Contraste"),
    ("artifacts", "Exposição/Artefatos"),
    ("positioning", "Posicionamento"),
    ("coverage", "Cobertura anatômica")
]

# `positioning` e `coverage` exigem entender ONDE está a anatomia na imagem
# (ex.: achados do YOLO espalhados pelo quadro vs. concentrados num canto).
# Sem um YOLO treinado (ver run_yolo_detection), não há como calcular isso
# de verdade — inventar um número aqui passaria confiança clínica que não
# existe, então esses critérios ficam "pending" até o modelo existir.
PENDING_CATEGORIES = {"positioning", "coverage"}

# Curvas calibradas em 2026-09 a partir dos percentis reais de ~500 imagens
# de dados/images/{train,valid} (sem rótulo de qualidade — é o corpus de
# treino do YOLO, usado aqui só como amostra do que uma radiografia "típica"
# parece, não como verdade absoluta). A pasta `test` do dataset foi excluída
# da calibração: suas imagens têm nitidez sistematicamente mais baixa
# (mediana de variância do Laplaciano ~3x menor que em train/valid),
# indício de que esse split passou por outro pipeline de redimensionamento/
# compressão — usá-lo enviesaria o limiar para "tudo parece borrado".
#
# Cada curva é uma função linear por partes (percentil -> score), não um
# min/max único: isso evita que a mediana do corpus já caia perto de 0 ou
# 100, mas ainda é só um ponto de partida. Ajuste com rótulos reais de
# "adequado/inadequado" assim que existirem (ver Fase 2: botão de feedback).
SHARPNESS_CURVE = [  # variância do filtro de Laplace (p2, p10, p50, p90, p98)
    (281.0, 10), (387.0, 30), (1087.0, 70), (1202.0, 92), (1258.0, 99)
]
CONTRAST_CURVE = [  # desvio padrão da intensidade normalizada (0-1)
    (0.190, 10), (0.214, 30), (0.243, 70), (0.276, 92), (0.295, 99)
]
CLIP_CURVE = [  # fração de pixels saturados (0 ou 255) — quanto menor, melhor
    (0.0025, 99), (0.0136, 92), (0.0398, 70), (0.0832, 30), (0.1124, 10)
]

MAX_DIMENSION = 768


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


def _piecewise_score(value: float, curve: list[tuple[float, float]]) -> int:
    """
    Interpola `value` numa curva (valor_da_métrica, score) ordenada por
    valor crescente. Fora dos extremos, estende a inclinação do segmento
    mais próximo e limita o resultado a [0, 100].
    """
    if value <= curve[0][0]:
        (x0, y0), (x1, y1) = curve[0], curve[1]
    elif value >= curve[-1][0]:
        (x0, y0), (x1, y1) = curve[-2], curve[-1]
    else:
        for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
            if x0 <= value <= x1:
                break

    ratio = (value - x0) / (x1 - x0) if x1 != x0 else 0.0
    score = y0 + ratio * (y1 - y0)
    return round(max(0.0, min(100.0, score)))


def _status_from_score(score: int) -> str:
    if score >= 75:
        return "approved"
    if score >= 55:
        return "attention"
    return "rejected"


def _load_grayscale_array(image_bytes: bytes) -> np.ndarray:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    width, height = image.size
    scale = MAX_DIMENSION / max(width, height)
    if scale < 1:
        image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))))
    return np.asarray(image, dtype=np.float32)


def _sharpness_metric(gray: np.ndarray) -> float:
    """Variância do filtro de Laplace: quanto mais borrada a imagem, menor a variância."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        # Imagem menor que o kernel 3x3 não tem textura suficiente para
        # medir nitidez — sem essa guarda, a fatia [1:-1,1:-1] fica vazia
        # e .var() devolve NaN, que se propaga como score inválido.
        return 0.0

    laplacian = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(laplacian.var())


def _contrast_metric(gray: np.ndarray) -> float:
    """Contraste RMS: desvio padrão da intensidade normalizada (0-1)."""
    return float((gray / 255.0).std())


def _clipping_metric(gray: np.ndarray) -> float:
    """Fração de pixels estourados (muito escuros ou muito claros) — indício de exposição ruim."""
    return float(np.mean((gray <= 3) | (gray >= 252)))


def run_efficientnet_adequacy(image_bytes: bytes) -> dict:
    """
    Controle de qualidade técnica — Fase 1: métricas clássicas de visão
    computacional, calculadas diretamente da imagem, sem machine learning e
    sem depender de dataset rotulado. `positioning` e `coverage` ficam como
    "pending" (ver PENDING_CATEGORIES) até existir um YOLO treinado para
    localizar a anatomia na imagem.

    O nome da função e o campo "model" seguem "efficientnet" apenas por
    compatibilidade com o restante da API — nenhuma rede neural roda aqui.
    Uma fase futura pode treinar um classificador real usando rótulos
    coletados via feedback dos usuários (Fase 2) combinados com estas
    mesmas métricas como features.
    """
    gray = _load_grayscale_array(image_bytes)

    metric_by_category = {
        "sharpness": _sharpness_metric(gray),
        "contrast": _contrast_metric(gray),
        "artifacts": _clipping_metric(gray)
    }

    score_by_category = {
        "sharpness": _piecewise_score(metric_by_category["sharpness"], SHARPNESS_CURVE),
        "contrast": _piecewise_score(metric_by_category["contrast"], CONTRAST_CURVE),
        "artifacts": _piecewise_score(metric_by_category["artifacts"], CLIP_CURVE)
    }

    criteria = []
    for key, label in QUALITY_CATEGORIES:
        if key in PENDING_CATEGORIES:
            criteria.append({
                "category": key,
                "label": label,
                "score": None,
                "status": "pending",
                "raw_value": None
            })
        else:
            criteria.append({
                "category": key,
                "label": label,
                "score": score_by_category[key],
                "status": _status_from_score(score_by_category[key]),
                "raw_value": round(metric_by_category[key], 4)
            })

    evaluated = [c for c in criteria if c["score"] is not None]
    overall_score = round(sum(c["score"] for c in evaluated) / len(evaluated)) if evaluated else 0
    is_adequate = overall_score >= 70 and all(c["status"] != "rejected" for c in evaluated)

    pending_labels = [c["label"] for c in criteria if c["status"] == "pending"]
    pending_note = (
        f" Critérios ainda não avaliados automaticamente (aguardam modelo treinado): {', '.join(pending_labels)}."
        if pending_labels else ""
    )

    recommendation = (
        "Qualidade técnica adequada nos critérios avaliados."
        if is_adequate else
        "Qualidade técnica abaixo do ideal — considere repetir a captura antes do laudo."
    ) + pending_note

    return {
        "model": "quality-heuristics-v1",
        "is_adequate": is_adequate,
        "score": overall_score,
        "criteria": criteria,
        "recommendation": recommendation
    }


def analyze_radiograph(image_bytes: bytes) -> dict:
    return {
        "yolo": run_yolo_detection(image_bytes),
        "efficientnet": run_efficientnet_adequacy(image_bytes)
    }
