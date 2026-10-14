# Publicação do AktIA num serviço só

O `Dockerfile` desta pasta gera uma imagem com o site e a API juntos: o frontend é
compilado e servido pela própria API, que roda com a IA ligada. Serve para qualquer
hospedagem que aceite contêiner Docker e ofereça cerca de 2 GB de memória.

## Como construir (Docker local)

A partir da raiz do repositório, para o contexto incluir as duas pastas do app:

```
docker build -f deploy/docker/Dockerfile -t aktia .
docker run -p 7860:7860 -e SUPABASE_URL=... -e SUPABASE_KEY=... aktia
```

## Variáveis de ambiente

| Variável | Valor |
|---|---|
| `SUPABASE_URL` | endereço do projeto Supabase |
| `SUPABASE_KEY` | chave `service_role` do projeto (secreta) |
| `PORT` | porta em que a API escuta (padrão 7860; o Cloud Run injeta a sua própria) |

Os pesos dos modelos são baixados do bucket privado `models` do Supabase na primeira análise.

## Publicação no Google Cloud Run

Usa o `cloudbuild.yaml` desta pasta para construir a imagem na nuvem (não precisa de
Docker local) e publica com a IA ligada. Exige uma conta Google Cloud com faturamento
ativado (cartão cadastrado); dentro da cota gratuita mensal, o uso típico deste site
não deve gerar cobrança, mas uso intenso pode custar.

```powershell
# Autenticação (uma vez por computador) e projeto.
gcloud auth login
gcloud config set project SEU_PROJETO_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Repositório de imagens (uma vez).
gcloud artifacts repositories create aktia --repository-format=docker --location=us-central1

# Build (a partir da raiz do repositório) e publicação.
gcloud builds submit --config deploy/docker/cloudbuild.yaml `
  --substitutions=_IMAGE=us-central1-docker.pkg.dev/SEU_PROJETO_ID/aktia/aktia .

gcloud run deploy aktia `
  --image=us-central1-docker.pkg.dev/SEU_PROJETO_ID/aktia/aktia `
  --region=us-central1 --platform=managed --allow-unauthenticated `
  --memory=2Gi --cpu=2 --cpu-boost --min-instances=0 --max-instances=2 `
  --set-env-vars=SUPABASE_URL=...,SUPABASE_KEY=...
```

`--min-instances=0` deixa o serviço "dormir" sem uso (sem custo quando ocioso), ao
preço de uma espera na primeira visita depois de um tempo parado, enquanto os
modelos carregam.
