# Publicação do AktIA num serviço só

O `Dockerfile` desta pasta gera uma imagem com o site e a API juntos: o frontend é
compilado e servido pela própria API, que roda com a IA ligada. Serve para qualquer
hospedagem que aceite contêiner Docker e ofereça cerca de 2 GB de memória.

Ainda não foi construído nem publicado em lugar nenhum.

## Como construir

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
| `PORT` | porta em que a API escuta (padrão 7860) |

Os pesos dos modelos são baixados do bucket privado `models` do Supabase na primeira análise.
