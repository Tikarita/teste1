# Imagem do backend com a IA ligada (classificador de qualidade + detector de
# achados). Precisa de cerca de 2 GB de memória: os dois modelos carregados e
# uma análise em andamento chegaram a 1,7 GB em teste local.
#
# Os pesos (.pt) não entram na imagem: são baixados do bucket privado
# MODELS_BUCKET do Supabase na primeira análise (app/services/model_store.py).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENABLE_AI=true \
    PORT=7860 \
    # O ultralytics grava configuração em disco; /tmp é gravável em qualquer host.
    YOLO_CONFIG_DIR=/tmp/ultralytics

# Bibliotecas de sistema que o OpenCV (dependência do ultralytics) carrega.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Usuário sem privilégios, com permissão de escrita em /app (onde os pesos são baixados).
RUN useradd --create-home --uid 1000 aktia
WORKDIR /app

COPY requirements-deploy.txt requirements-ai.txt ./
RUN pip install -r requirements-deploy.txt \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 torchvision==0.29.0 \
    && pip install -r requirements-ai.txt

COPY --chown=aktia:aktia app ./app
RUN chown aktia:aktia /app
USER aktia

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
