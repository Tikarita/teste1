# AktIA — histórico e estado do projeto

Resumo para quem (pessoa ou assistente) for continuar o trabalho sem ter acompanhado a
sessão de desenvolvimento de 5 a 9 de outubro de 2026. Atualizado em 9 de outubro de 2026.

## O que é

Plataforma de controle de qualidade de radiografias odontológicas panorâmicas. O profissional
envia a radiografia, a IA classifica a qualidade (adequada ou inadequada), sugere achados
clínicos para um pré-laudo, e o sistema registra tudo para o Programa de Garantia da Qualidade
exigido pela ANVISA (RDC 611/2022).

## Onde está cada coisa

- **Backend:** `aktia-backend/` — Python, FastAPI (`app/main.py`, `app/api`, `app/services`, `app/schemas`).
- **Frontend:** `aktia-frontend/` — React, TypeScript, Tailwind, Vite.
- **Banco:** Supabase (PostgreSQL + Storage), projeto `aktia`. Migrations em `supabase/migrations/`;
  o schema real, reconstruído do banco, está em `docs/database/schema.sql`.
- **Modelos de IA:** `aktia-backend/app/ml/`. Os arquivos `.pt` ficam fora do Git.
- **Dataset e scripts de treino:** raiz do repositório (`dados/`, `train_*.py`).
- **Regras do projeto:** `CLAUDE.md`, na raiz.

O trabalho está na branch `etapa-2-qualidade`. A `main` e o site publicado (Vercel + Render)
ainda têm a versão antiga, sem IA.

## O que foi construído

1. **Segurança e isolamento.** Todas as rotas de dados exigem login; a clínica vem sempre do
   usuário autenticado. O bucket de radiografias, que estava aberto a qualquer pessoa, foi fechado.
2. **Qualidade da imagem.** EfficientNet-B0 supervisionado. No conjunto de teste: 77,9% de
   acurácia e 58,9% de recall para "inadequado". O score é a probabilidade de adequação (0–100).
3. **Explicação visual.** Mapa de calor (Grad-CAM) mostrando onde a IA se apoiou.
4. **Pré-laudo.** YOLOv8m com 14 classes de achados (mAP50 0,537; BON, APS, FUR, API e CAR são
   fracas). Os achados aparecem agrupados por tipo, depois da classificação de qualidade; em
   imagem inadequada o pré-laudo fica bloqueado, com opção de abrir mesmo assim.
5. **Validação pelo dentista.** Cada achado é confirmado ou descartado; só os confirmados entram
   no pré-laudo emitido.
6. **Pré-laudo emitido.** Documento para impressão/PDF nos formatos ESR e ACR (as duas
   diretrizes de estrutura de laudo radiológico). A impressão diagnóstica é escrita pelo
   dentista, nunca pela IA. O documento fica congelado depois de emitido.
7. **Revisão humana da qualidade.** O profissional registra adequado/inadequado, motivos e se o
   exame foi repetido. É a base da taxa de rejeição real.
8. **Avisos em tempo real.** Exame classificado como inadequado gera alerta no canto da tela,
   contador no cabeçalho e notificação do sistema operacional, para o responsável e para quem
   enviou. "Ciente" registra a leitura.
9. **Envio automático.** Escolher ou arrastar o arquivo já envia, abre o exame e classifica.
   Aceita JPG, PNG e DICOM (o DICOM é convertido para PNG; dados do paciente não são guardados).
10. **Estatísticas no backend.** Dashboard, perfil por profissional, acerto do detector e
    indicadores de revisão, todos calculados no banco. Sem amostra mínima (5), o valor é nulo
    com a marca "dados insuficientes", nunca zero.
11. **Relatório de Garantia da Qualidade.** Emitido por período, congelado, com layout de impressão.

## Decisões tomadas

- **LGPD:** o paciente é identificado só pelo código do prontuário. Nome, CPF e data de
  nascimento não são guardados, e o arquivo DICOM original é descartado.
- **Nunca inventar resultado de IA.** O detector anterior fabricava achados e foi removido.
- **Métricas automáticas de nitidez, contraste e exposição foram descontinuadas.** Validadas
  contra 5.012 imagens rotuladas, não distinguiam imagem boa de ruim (AUC entre 0,45 e 0,49).
- **O aviso de exame inadequado pede para conferir a imagem antes de refazer**, porque a IA
  marca como inadequada cerca de 1 em cada 8 imagens boas.
- **Papéis de usuário:** `admin`, `manager` e `user`, os que o banco aceita.
- **Qualquer profissional da clínica pode revisar e validar;** só admin e gestor emitem o
  relatório de qualidade e veem o perfil dos colegas.

## Estado atual

- 190 testes automáticos do backend passando (`pytest` em `aktia-backend`, com Postgres embutido).
- 9 migrations aplicadas no banco real.
- Tudo roda localmente: backend em `http://localhost:8000`, frontend em `http://localhost:5173`.
- Existe uma clínica de teste no banco ("Clínica de Teste (AktIA)") com exames, relatórios e
  pré-laudos de demonstração.

## Pendências

1. **Enviar a branch ao GitHub e publicar.** Falta decidir onde os modelos de IA rodam em
   produção (o plano gratuito do Render não comporta os dois) e como os `.pt` chegam ao servidor.
2. **Validar o DICOM com um exame real do aparelho da clínica.** A conversão foi testada com
   radiografias embrulhadas em DICOM; mudanças de contraste alteram o resultado da IA.
3. **Número do dente em cada achado** (exige treinar o modelo de numeração).
4. **CRO no cadastro do profissional** e **histórico por paciente** (para a seção "Comparação").
5. **Registro dos testes de equipamento da IN 94/2021.**
6. **Fase B do DICOM:** receber o exame direto do aparelho.
7. **Limpar os dados de teste** e as tabelas sem uso (`users`, `user_profiles`, `exams`).
8. **Confirmar com um dentista** o significado das 14 siglas de achados, hoje num mapeamento provisório.

## Como rodar

```
cd aktia-backend
pip install -r requirements.txt        # com IA; requirements-deploy.txt sem IA
uvicorn app.main:app --port 8000

cd aktia-frontend
npm install
npm run dev
```

O backend precisa de `aktia-backend/.env` com `SUPABASE_URL`, `SUPABASE_KEY` (service role) e
`ENABLE_AI=true`, e dos dois arquivos `.pt` em `aktia-backend/app/ml/`. Migrations novas são
aplicadas com `supabase db push`.
