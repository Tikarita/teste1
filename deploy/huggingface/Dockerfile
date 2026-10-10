# AktIA completo num serviço só: o frontend é compilado e servido pela própria
# API, que roda com a IA ligada. Feito para o Hugging Face Spaces (Docker).
#
# Precisa de cerca de 2 GB de memória: os dois modelos carregados e uma análise
# em andamento chegaram a 1,7 GB em teste local. Os pesos (.pt) não entram na
# imagem: são baixados do bucket privado MODELS_BUCKET do Supabase na primeira
# análise (app/services/model_store.py).

# --- 1. Frontend ---------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build

COPY aktia-frontend/package.json aktia-frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY aktia-frontend/ ./
# Mesmo endereço da API: caminho relativo, sem CORS.
ENV VITE_API_URL=/api/v1 \
    VITE_ENABLE_AI=true
RUN npm run build

# --- 2. Backend com a IA ---------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENABLE_AI=true \
    PORT=7860 \
    FRONTEND_DIST=/app/frontend \
    # O ultralytics grava configuração em disco; /tmp é gravável em qualquer host.
    YOLO_CONFIG_DIR=/tmp/ultralytics

# Bibliotecas de sistema que o OpenCV (dependência do ultralytics) carrega.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Usuário sem privilégios, com escrita em /app (onde os pesos são baixados).
RUN useradd --create-home --uid 1000 aktia
WORKDIR /app

COPY aktia-backend/requirements-deploy.txt aktia-backend/requirements-ai.txt ./
# O torch entra na versão só-CPU: a padrão do pip no Linux traz as bibliotecas
# de GPU e passa de 2 GB.
RUN pip install -r requirements-deploy.txt \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 torchvision==0.29.0 \
    && pip install -r requirements-ai.txt

COPY --chown=aktia:aktia aktia-backend/app ./app
COPY --chown=aktia:aktia --from=frontend /build/dist ./frontend
RUN chown aktia:aktia /app
USER aktia

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
