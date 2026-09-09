-- Rode isso no SQL Editor do Supabase para o resultado da análise
-- (YOLOv8 + EfficientNet) persistir na radiografia e aparecer no
-- Dashboard/lista sem precisar reanalisar a cada visita.

alter table radiographs
  add column if not exists analysis_result jsonb;
