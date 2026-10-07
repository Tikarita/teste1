# Mapeamento provisório dos 14 códigos de classe do dataset de treino
# (dados/data.yaml). Ainda não há confirmação oficial do significado de
# cada sigla — revise antes de usar em laudo real.
#
# Fica num módulo sem dependência de torch para as estatísticas poderem usar
# os rótulos mesmo com a IA desligada (ENABLE_AI=false).
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

# Classes em que o detector teve desempenho fraco no conjunto de teste. Os
# achados delas vão marcados para a tela avisar quem lê.
LOW_RELIABILITY_CLASSES = {"BON", "APS", "FUR", "API", "CAR"}
