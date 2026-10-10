# AktIA — backend

API (FastAPI) da plataforma AktIA, com a classificação de qualidade e a detecção de
achados em radiografias odontológicas.

## Variáveis de ambiente

| Variável | Valor |
|---|---|
| `SUPABASE_URL` | endereço do projeto Supabase |
| `SUPABASE_KEY` | chave `service_role` do projeto (secreta) |
| `ENABLE_AI` | `true` roda os modelos; `false` sobe a API sem o torch |
| `CORS_ORIGINS` | endereço do frontend, quando ele fica em outro domínio |
| `FRONTEND_DIST` | pasta do frontend compilado, para a API servir o site também |

Os pesos dos modelos ficam fora do Git. Sem eles em `app/ml/`, são baixados do bucket
privado `models` do Supabase na primeira análise.

## Rodar localmente

```
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

A publicação em produção está descrita em `deploy/huggingface/`.
