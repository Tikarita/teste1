-- Dados técnicos do exame --------------------------------------------------------
-- Quando a radiografia chega como DICOM, o backend guarda aqui os dados
-- técnicos lidos do arquivo: data do exame, tipo, aparelho e parâmetros de
-- exposição. Dados do paciente não são gravados, e o arquivo DICOM original
-- não é armazenado (só a imagem convertida).
--
-- Só adiciona uma coluna.

alter table public.radiographs
  add column if not exists exam_metadata jsonb;
