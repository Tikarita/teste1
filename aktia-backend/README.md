---
title: AktIA API
emoji: 🦷
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# AktIA — backend

API (FastAPI) da plataforma AktIA, com a classificação de qualidade e a detecção de
achados em radiografias odontológicas.

O cabeçalho acima é a configuração do Hugging Face Spaces, onde este diretório é
publicado como um Space do tipo Docker (ver `Dockerfile`).

## Variáveis de ambiente (segredos do Space)

| Variável | Valor |
|---|---|
| `SUPABASE_URL` | endereço do projeto Supabase |
| `SUPABASE_KEY` | chave `service_role` do projeto (secreta) |
| `CORS_ORIGINS` | endereço do frontend, por exemplo `https://aktia.vercel.app` |

`ENABLE_AI=true` e `PORT=7860` já vêm definidos na imagem. Os pesos dos modelos são
baixados do bucket privado `models` do Supabase na primeira análise.

## Rodar localmente

```
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Precisa de um arquivo `.env` com as variáveis acima e `ENABLE_AI=true`.
