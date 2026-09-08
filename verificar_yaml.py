# verificar_yaml.py
from pathlib import Path
import os

print("🔍 Procurando data.yaml...\n")

# Verifica pasta atual
print(f"Pasta atual: {os.getcwd()}\n")

# Procura em todos os lugares
for yaml_path in Path(".").rglob("data.yaml"):
    print(f"✅ Encontrado: {yaml_path.absolute()}")

# Verifica pasta dados
dados_path = Path("dados")
if dados_path.exists():
    print(f"\n📁 Pasta 'dados' existe: {dados_path.absolute()}")
    print(f"   Conteúdo: {list(dados_path.iterdir())}")
    
    yaml_dados = dados_path / "data.yaml"
    print(f"   data.yaml existe: {yaml_dados.exists()}")
else:
    print(f"\n❌ Pasta 'dados' NÃO existe")

# Verifica pasta antiga
old_path = Path("panoramic_radiography_yolo_dataset_14_classes")
if old_path.exists():
    print(f"\n📁 Pasta 'panoramic_radiography_yolo_dataset_14_classes' existe: {old_path.absolute()}")
    yaml_old = old_path / "data.yaml"
    print(f"   data.yaml existe: {yaml_old.exists()}")