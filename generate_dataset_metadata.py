"""Gera metadata/dataset_info.json e LICENSE.txt para cada dataset em AKTIA_DATASETS/,
com base na verificacao de licenca/acesso feita manualmente (WebFetch/WebSearch) em 2026-09-17.
"""
import json
from pathlib import Path
from datetime import date

today = str(date.today())
BASE = Path("AKTIA_DATASETS")

datasets = {
    "01_Panoramic_Dental_Xray": {
        "name": "Panoramic Dental Xray Dataset",
        "source_url": "https://data.mendeley.com/datasets/73n3kz2k4k/3",
        "version": "3",
        "license": "CC BY 4.0",
        "commercial_use": "COMMERCIAL_WITH_CONDITIONS",
        "images_count": 221,
        "image_formats": ["resolucoes variam: 1024x512, 2888x1309, 2964x1464"],
        "has_annotations": True,
        "annotation_format": "Parte 1: tooth instance segmentation. Parte 2: classificacao por 8 tipos dentarios. Parte 3: apenas imagens alta resolucao, sem anotacao. Formato exato de arquivo nao confirmado (Mendeley bloqueado nesta rede) - confirmar apos download manual.",
        "recommended_for": ["EfficientNet (fonte de imagens)", "YOLO (avaliar anotacoes da parte 1/2 apos download)"],
        "restrictions": "Atribuicao obrigatoria (CC BY 4.0). Autores: Walid Brahmi, Imen Jdey, Fadoua Drira (Universite de Kairouan).",
        "download_date": None,
        "download_status": "BLOCKED_NETWORK - data.mendeley.com inacessivel desta rede (firewall institucional). Download manual necessario.",
        "authors": "Walid Brahmi, Imen Jdey, Fadoua Drira",
        "doi": "10.17632/73n3kz2k4k.3",
    },
    "02_Periapical_Lesions": {
        "name": "Panoramic radiographs with periapical lesions Dataset",
        "source_url": "https://data.mendeley.com/datasets/kx52tk2ddj/3",
        "version": "3",
        "license": "CC BY 4.0",
        "commercial_use": "COMMERCIAL_WITH_CONDITIONS",
        "images_count": 3926,
        "image_formats": ["jpg"],
        "has_annotations": True,
        "annotation_format": "Pasta 'Image Annotations' mencionada na pagina; formato exato (XML/COCO/outro) NAO confirmado - Mendeley bloqueado nesta rede.",
        "recommended_for": ["YOLO (deteccao de lesao periapical - PRIORITARIO)", "EfficientNet (fonte de imagens, SEM label de qualidade automatico)"],
        "restrictions": "Atribuicao obrigatoria (CC BY 4.0). Autor: Viet Do, Hanoi Medical University. ALERTA DATA LEAKAGE: a pagina indica que as imagens foram expandidas atraves de aumentacao de dados - identificar originais vs. aumentadas ANTES de qualquer split train/test.",
        "download_date": None,
        "download_status": "BLOCKED_NETWORK - data.mendeley.com inacessivel desta rede. Download manual necessario.",
        "authors": "Viet Do (Hanoi Medical University)",
        "doi": "10.17632/kx52tk2ddj.3",
    },
    "03_Panoramic_Mandibles_V1": {
        "name": "Panoramic Dental X-rays With Segmented Mandibles",
        "source_url": "https://data.mendeley.com/datasets/hxt48yk462/1",
        "version": "1 (CONFIRMADO - NAO usar V2, que tem licenca nao-comercial)",
        "license": "CC BY 4.0",
        "commercial_use": "COMMERCIAL_WITH_CONDITIONS",
        "images_count": 116,
        "image_formats": ["formato nao confirmado - Mendeley bloqueado"],
        "has_annotations": True,
        "annotation_format": "Mascaras de segmentacao de mandibula, anotadas manualmente por 2 dentistas. Formato de arquivo nao confirmado.",
        "recommended_for": ["EfficientNet (fonte de imagens)", "YOLO/segmentacao (regiao mandibular)"],
        "restrictions": "Atribuicao obrigatoria (CC BY 4.0). So a V1 tem essa licenca - a V2 e CC BY-NC (nao comercial). Autores: Amir Abdi, Shohreh Kasaei; Noor Medical Imaging Center, Qom, Ira.",
        "download_date": None,
        "download_status": "BLOCKED_NETWORK - data.mendeley.com inacessivel desta rede. Download manual necessario (garantir URL da V1, nao V2).",
        "authors": "Amir Abdi, Shohreh Kasaei",
        "doi": "10.17632/hxt48yk462.1",
    },
    "04_Dental_Radiography": {
        "name": "Dental Radiography",
        "source_url": "https://www.kaggle.com/datasets/imtkaggleteam/dental-radiography",
        "version": "nao versionado explicitamente - ultima atualizacao 2023-10-07",
        "license": "UNKNOWN",
        "commercial_use": "REQUIRES_PERMISSION",
        "images_count": None,
        "image_formats": ["jpg (provavel)"],
        "has_annotations": "nao confirmado",
        "annotation_format": "nao confirmado - possivelmente bounding boxes de carie dado o uso mencionado para CNN/YOLO/SSD, mas nao verificado diretamente.",
        "recommended_for": ["EfficientNet - PENDENTE confirmacao de licenca", "YOLO - PENDENTE verificar anotacoes"],
        "restrictions": "Licenca NAO confirmada. Kaggle e uma SPA que nao pode ser lida por WebFetch nem por scraping simples, e esta rede nao tem acesso direto a kaggle.com. Estrutura conhecida: pastas Train/Test/Valid dentro de um zip - nao misturar os splits sem entender como foram construidos.",
        "download_date": None,
        "download_status": "BLOCKED_NETWORK + BLOCKED_AUTH - kaggle.com inacessivel desta rede E nao ha credenciais da Kaggle API nesta maquina. Requer login manual + confirmar licenca visualmente.",
        "authors": "imtkaggleteam (uploader Kaggle, nao necessariamente autor original)",
        "doi": None,
    },
    "05_DENTEX": {
        "name": "DENTEX Challenge 2023 Dataset",
        "source_url": "https://zenodo.org/records/7812323",
        "version": "v1",
        "license": "CC BY 4.0",
        "commercial_use": "COMMERCIAL_WITH_CONDITIONS",
        "images_count": 3337,
        "image_formats": ["a confirmar apos download"],
        "has_annotations": True,
        "annotation_format": "COCO JSON hierarquico: quadrante (693 imgs), quadrante+numeracao (634 imgs), quadrante+numeracao+diagnostico (1005 imgs - classes: caries, deep caries, periapical lesion, impacted tooth), + 1571 imagens sem anotacao para pre-treino.",
        "recommended_for": ["YOLO (deteccao de patologia - PRIORITARIO, melhor base anotada do lote)", "EfficientNet (fonte de imagens, SEM label de qualidade automatico)"],
        "restrictions": "Atribuicao obrigatoria (CC BY 4.0). Licenca confirmada diretamente na pagina oficial do Zenodo.",
        "download_date": None,
        "download_status": "BLOCKED_NETWORK - zenodo.org inacessivel desta rede. URLs diretas confirmadas: training_data.zip (10.9 GB), validation_data.zip (149.5 MB), total 11.1 GB.",
        "authors": "DENTEX Challenge organizers (MICCAI 2023)",
        "doi": "10.5281/zenodo.7812323",
        "direct_download_urls": [
            "https://zenodo.org/records/7812323/files/training_data.zip?download=1",
            "https://zenodo.org/records/7812323/files/validation_data.zip?download=1",
        ],
    },
    "06_Tufts": {
        "name": "Tufts Dental Database (TDD)",
        "source_url": "https://tdd.ece.tufts.edu/",
        "version": "nao versionado explicitamente",
        "license": "REQUIRES_PERMISSION - nao confirmada diretamente no site oficial. Mirror de terceiros no Kaggle cita Attribution-NonCommercial-ShareAlike 3.0 IGO (CC BY-NC-SA 3.0 IGO), que indicaria uso nao-comercial proibido, mas isso NAO foi confirmado na fonte primaria.",
        "commercial_use": "REQUIRES_PERMISSION",
        "images_count": 1000,
        "image_formats": ["jpg, 1615x840px"],
        "has_annotations": True,
        "annotation_format": "Labelbox JSON: teeth_bbox.json e teeth_polygon.json (numeracao dentaria 1-32 permanentes + A-T deciduos), teeth_mask/ e maxillomandibular/ (mascaras), student.json (classificacao de lesao: Periapical/Pericoronal/Inter-Radicular/Non-Odontogenic).",
        "recommended_for": ["VER ALERTA CRITICO abaixo antes de recomendar qualquer uso"],
        "restrictions": "ALERTA CRITICO: este e o mesmo dataset que o usuario ja tinha baixado manualmente (pasta local 'Downloads/Novos dados') e que ja foi parcialmente incorporado ao projeto ANTES desta verificacao de licenca: build_teeth_numbering_dataset.py gerou dados_dentes/, e add_novos_dados_images.py copiou as 1000 imagens (prefixo nd_) para dados/images/. Ate confirmar a licenca diretamente com Tufts (contato: panettavisonsensinglab@gmail.com, ou releitura do paper IEEE Panetta et al. 2021), NAO treinar/publicar modelo comercial usando essas imagens.",
        "download_date": None,
        "download_status": "JA_DISPONIVEL_LOCALMENTE (fornecida pelo usuario, nao baixada nesta sessao) - tdd.ece.tufts.edu tambem esta BLOCKED_NETWORK nesta rede.",
        "authors": "Panetta, K., Rajendran, R., Ramesh, A., Rao, S. P., Agaian, S. - Tufts University School of Dental Medicine (IRB MODCR-01-12631)",
        "doi": None,
    },
    "07_Panoramic_Caries": {
        "name": "Panoramic-Caries-Segmentation / DC1000 (MLUA)",
        "source_url": "https://github.com/Zzz512/MLUA",
        "version": "nao versionado",
        "license": "UNKNOWN - sem arquivo LICENSE no repositorio. README apenas pede citacao do paper (Wang et al. 2023, Neurocomputing) se o dataset for usado.",
        "commercial_use": "REQUIRES_PERMISSION",
        "images_count": None,
        "image_formats": ["nao confirmado - dataset DC1000 nao baixado"],
        "has_annotations": True,
        "annotation_format": "Segmentacao de carie (mascaras) - formato exato nao confirmado sem baixar o dataset.",
        "recommended_for": ["YOLO/segmentacao (carie) - PENDENTE autorizacao dos autores"],
        "restrictions": "Sem licenca explicita = uso comercial NAO autorizado ate contato direto com os autores. Codigo clonado para referencia (raw/MLUA/); dataset DC1000 (Google Drive/Baidu) NAO baixado por falta de licenca clara.",
        "download_date": today,
        "download_status": "CODIGO_CLONADO (github.com acessivel) - DATASET_NAO_BAIXADO (Google Drive acessivel tecnicamente, download adiado por falta de licenca clara).",
        "authors": "Wang, Gao, Jiang, Zhang, Wang, Chen, Yu, Yang",
        "doi": None,
        "dataset_links": [
            "https://drive.google.com/file/d/1Xn1oGHvhGF9GbkcLEtCOV5QvWWqt1y62/view?usp=drive_link",
            "https://pan.baidu.com/s/1jRXsSQIr8mm3EyGYELv9kg?pwd=rsoc",
        ],
    },
    "08_TK_Tooth_Number": {
        "name": "TK_Tooth_Number_Code",
        "source_url": "https://github.com/tanjidakabir/TK_Tooth_Number_Code",
        "version": "nao versionado",
        "license": "UNKNOWN - sem arquivo LICENSE, sem mencao no README.",
        "commercial_use": "REQUIRES_PERMISSION",
        "images_count": 40,
        "image_formats": ["jpg (apenas sample_images, nao e um dataset completo)"],
        "has_annotations": False,
        "annotation_format": "Nenhum arquivo padrao de bounding box (COCO/PASCAL/YOLO). Contem planilhas Excel e modelos .h5 pre-treinados, sem dataset anotado real anexado.",
        "recommended_for": ["NENHUM - nao ha dataset utilizavel, apenas codigo/templates de referencia"],
        "restrictions": "Repositorio nao contem dataset de treino real - apenas 40 imagens de amostra e modelos .h5 prontos. Baixo valor pratico alem de referencia de abordagem.",
        "download_date": today,
        "download_status": "CLONADO (repositorio completo, 19MB)",
        "authors": "Tanjida Kabir",
        "doi": None,
    },
    "09_CTooth": {
        "name": "CTooth+ dataset (CBCT)",
        "source_url": "https://www.kaggle.com/datasets/weiweicui/ctooth-dataset",
        "version": "nao aplicavel",
        "license": "CC BY-NC 4.0 (confirmado via lista curada de terceiros + paper arXiv:2208.01643 - NAO confirmado diretamente na pagina Kaggle, que estava inacessivel)",
        "commercial_use": "NON_COMMERCIAL",
        "images_count": None,
        "image_formats": ["CBCT volumes 3D - NAO e radiografia panoramica 2D"],
        "has_annotations": True,
        "annotation_format": "22 volumes totalmente anotados + 146 nao anotados, segmentacao de volume dentario.",
        "recommended_for": ["NENHUM para o AktIA - modalidade errada (CBCT 3D) e licenca nao-comercial"],
        "restrictions": "NAO USAR EM PRODUTO COMERCIAL. Nao prioritario conforme definido pelo usuario. Nao baixado.",
        "download_date": None,
        "download_status": "NAO_BAIXADO - nao prioritario + licenca nao-comercial + modalidade incompativel + kaggle.com bloqueado nesta rede.",
        "authors": "Weiwei Cui et al.",
        "doi": None,
    },
}

for folder, info in datasets.items():
    d = BASE / folder / "metadata"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "dataset_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    with open(BASE / folder / "LICENSE.txt", "w", encoding="utf-8") as f:
        f.write(f"Dataset: {info['name']}\n")
        f.write(f"Fonte: {info['source_url']}\n")
        f.write(f"Versao: {info['version']}\n")
        f.write(f"Licenca declarada: {info['license']}\n")
        f.write(f"Classificacao de uso comercial: {info['commercial_use']}\n")
        f.write(f"Restricoes/observacoes: {info['restrictions']}\n")
        f.write(f"Verificado em: {today}\n")

print(f"Metadata e LICENSE.txt gerados para {len(datasets)} datasets")
