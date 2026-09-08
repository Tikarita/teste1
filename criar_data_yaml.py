# criar_data_yaml.py
import yaml
from pathlib import Path

# Classes do dataset
CLASSES = [
    "IMP",   # Implant
    "PRR",   # Prosthetic Restoration
    "OBT",   # Obturation
    "END",   # Endodontic Treatment
    "CAR",   # Carious Lesion
    "BON",   # Bone Resorption
    "IMT",   # Impacted Tooth
    "API",   # Apical Periodontitis
    "ROT",   # Root Fragment
    "FUR",   # Furcation Lesion
    "APS",   # Apical Surgery
    "ROR",   # Root Resorption
    "ORD",   # Orthodontic Device
    "SRD",   # Surgical Device
]

# Configurações
DATASET_DIR = "dados"
yaml_path = Path(DATASET_DIR) / "data.yaml"

# Cria o dicionário
data = {
    "path": DATASET_DIR,
    "train": "images/train",
    "val": "images/valid",
    "test": "images/test",
    "nc": len(CLASSES),
    "names": CLASSES
}

# Salva o YAML
yaml_path.parent.mkdir(parents=True, exist_ok=True)
with open(yaml_path, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print(f"✅ data.yaml criado em: {yaml_path.absolute()}")
print(f"\n📄 Conteúdo:")
print("-" * 60)
with open(yaml_path, 'r', encoding='utf-8') as f:
    print(f.read())
print("-" * 60)