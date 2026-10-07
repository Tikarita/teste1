# AktIA — Contexto do projeto

## Fonte de verdade do banco
- O banco é Supabase/PostgreSQL e JÁ EXISTE em produção.
- Você tem acesso de LEITURA ao banco real via MCP do Supabase (ferramentas mcp__supabase__*). Use-as para conferir tabelas, colunas, FKs e políticas RLS antes de propor qualquer mudança.
- Também existe um dump de apoio em docs/database/schema.sql.
- NUNCA presuma nomes de tabela, coluna ou relacionamento. Se tiver dúvida, consulte o banco via MCP.
- Nomes de tabelas/colunas citados em pedidos são SUGESTÕES CONCEITUAIS — procure o equivalente real antes de criar algo novo.

## Regras para mudanças no banco
- Somente migrations aditivas em supabase/migrations/ (nada de DROP, rename ou mudança de tipo em coluna existente).
- Antes de criar uma migration: mostre o SQL, explique o motivo e o impacto, e AGUARDE aprovação explícita.
- Toda tabela nova: clinic_id + FK, índices e RLS no mesmo padrão das tabelas existentes.

## Stack
- Backend: Python + FastAPI (app/main.py, api, core, services, models)
- Banco/Storage: Supabase
- Frontend: React + TypeScript + Tailwind

## Regras gerais
- Não recriar nem remover o que já funciona; reutilizar componentes, serviços e endpoints.
- Backend é a única fonte de verdade para scores e agregações.
- Nunca inventar resultados de IA ou números.
- clinic_id sempre vem do usuário autenticado, nunca do request.
