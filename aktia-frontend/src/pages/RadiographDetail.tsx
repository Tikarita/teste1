import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import Heatmap from "../components/Heatmap";
import { REFRESH_NOTIFICATIONS_EVENT } from "../components/NotificationCenter";
import { colorFor } from "../lib/findingColors";
import ReviewCard from "../components/ReviewCard";
import type {
  AnalysisResult,
  FindingDecision,
  FindingValidation,
  PreReportSummary,
  Radiograph,
  Review
} from "../lib/types";

// VITE_ENABLE_AI=false esconde a análise enquanto a IA não está no ar.
const AI_ENABLED = import.meta.env.VITE_ENABLE_AI !== "false";

// Rótulos dos dados técnicos que vêm do DICOM, na ordem em que aparecem.
const EXAM_METADATA_LABELS: [string, string][] = [
  ["exam_date", "Data do exame"],
  ["modality", "Modalidade"],
  ["manufacturer", "Fabricante"],
  ["model", "Modelo do aparelho"],
  ["station_name", "Estação"],
  ["body_part", "Região examinada"],
  ["kvp", "Tensão (kV)"],
  ["tube_current_ma", "Corrente (mA)"],
  ["exposure_time_ms", "Tempo de exposição (ms)"],
  ["exposure_mas", "Exposição (mAs)"],
  ["dose_area_product", "Produto dose-área"],
  ["software_version", "Versão do software"]
];

/** O que está em destaque na imagem: um tipo inteiro ou um achado específico. */
type Highlight = { code: string; index: number | null } | null;

export default function RadiographDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [radiograph, setRadiograph] = useState<Radiograph | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [validations, setValidations] = useState<FindingValidation[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [preReports, setPreReports] = useState<PreReportSummary[]>([]);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [issueFormOpen, setIssueFormOpen] = useState(false);
  const [issueFormat, setIssueFormat] = useState<"esr" | "acr">("esr");
  const [issueForm, setIssueForm] = useState({
    exam_type: "Radiografia panorâmica",
    requested_by: "",
    clinical_indication: "",
    impression: "",
    notes: ""
  });
  const [editingCode, setEditingCode] = useState(false);
  const [codeDraft, setCodeDraft] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [highlighted, setHighlighted] = useState<Highlight>(null);

  // Achados só aparecem quando vieram de um modelo real (ver YoloResult.available).
  const detected = analysis?.yolo.available ? analysis.yolo.findings : [];
  const findingsAvailable = analysis?.yolo.available === true;

  // ?mapa=1 (link do aviso pós-envio) já abre com o mapa de calor ligado.
  const [searchParams] = useSearchParams();
  const [showHeatmap, setShowHeatmap] = useState(searchParams.get("mapa") === "1");
  const [expanded, setExpanded] = useState(false);
  const [openAnyway, setOpenAnyway] = useState(false);

  // Etapa 1 decide a etapa 2: a IA libera o pré-laudo quando considera a
  // imagem adequada. A revisão do profissional, quando existe, prevalece.
  const quality = analysis?.efficientnet ?? null;
  const qualityOk = review ? review.verdict === "adequate" : quality?.is_adequate === true;
  const preReportOpen = qualityOk || openAnyway;
  const explanation = analysis?.efficientnet.explanation ?? null;

  function load() {
    if (!id) return;
    setLoading(true);
    setError(null);

    api
      .getRadiograph(id)
      .then((res) => {
        setRadiograph(res.data);
        setAnalysis(res.data.analysis_result ?? null);
        setReview(res.review ?? null);
        setValidations(res.finding_validations ?? []);
        api.listPreReports(res.data.id).then(setPreReports).catch(() => setPreReports([]));
        const url = res.signed_url?.signedUrl ?? res.signed_url?.signedURL ?? null;
        setImageUrl(url && url.startsWith("http") ? url : null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar radiografia"))
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  // Vindo do envio (?analisar=1), a classificação começa sozinha assim que o
  // exame carrega. A referência evita disparar de novo se a tela re-renderizar.
  const autoAnalyzed = useRef(false);
  useEffect(() => {
    if (autoAnalyzed.current || loading || !radiograph) return;
    if (searchParams.get("analisar") !== "1" || !AI_ENABLED || radiograph.analysis_result) return;

    autoAnalyzed.current = true;
    void handleAnalyze();
  }, [loading, radiograph]);

  async function handleAnalyze() {
    if (!id) return;
    setAnalyzing(true);
    setAnalyzeError(null);

    try {
      const res = await api.analyzeRadiograph(id);
      setAnalysis(res.data);
      // Análise nova, lista de achados nova: a validação recomeça.
      setValidations([]);
      // Se o exame saiu inadequado, o backend gerou um aviso: busca na hora,
      // em vez de esperar a próxima checagem periódica.
      window.dispatchEvent(new Event(REFRESH_NOTIFICATIONS_EVENT));
    } catch (err) {
      setAnalyzeError(err instanceof ApiError ? err.message : "Erro ao analisar radiografia");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleDelete() {
    if (!id || !confirm("Excluir esta radiografia?")) return;
    setDeleting(true);

    try {
      await api.deleteRadiograph(id);
      navigate("/radiografias");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao excluir radiografia");
      setDeleting(false);
    }
  }

  // As caixas só aparecem quando o pré-laudo está liberado (ou aberto mesmo assim).
  const findings = preReportOpen ? detected : [];

  // Pré-laudo agrupado por tipo de achado, do mais frequente para o menos.
  const groups = [
    ...detected
      .reduce((byCode, finding, index) => {
        const group = byCode.get(finding.class_code) ?? {
          code: finding.class_code,
          label: finding.label,
          lowReliability: finding.low_reliability === true,
          items: [] as { finding: (typeof detected)[number]; index: number }[]
        };
        group.items.push({ finding, index });
        return byCode.set(finding.class_code, group);
      }, new Map<string, { code: string; label: string; lowReliability: boolean; items: { finding: (typeof detected)[number]; index: number }[] }>())
      .values()
  ].sort((a, b) => b.items.length - a.items.length || a.label.localeCompare(b.label));

  const decisionByIndex = new Map(validations.map((v) => [v.finding_index, v.decision]));
  const pendingCount = detected.filter((_, index) => !decisionByIndex.has(index)).length;

  // Grava a decisão sobre um ou mais achados. Repetir a decisão já tomada a desfaz.
  async function decide(indexes: number[], decision: FindingDecision) {
    if (!id || indexes.length === 0) return;
    setValidationError(null);

    const undo = indexes.length === 1 && decisionByIndex.get(indexes[0]) === decision;

    try {
      setValidations(
        await api.validateFindings(
          id,
          indexes.map((finding_index) => ({ finding_index, decision: undo ? "pending" : decision }))
        )
      );
    } catch (err) {
      setValidationError(err instanceof ApiError ? err.message : "Erro ao salvar a validação");
    }
  }

  async function issuePreReport() {
    if (!id) return;
    setIssuing(true);
    setIssueError(null);

    try {
      const issued = await api.createPreReport({ radiograph_id: id, report_format: issueFormat, ...issueForm });
      navigate(`/pre-laudos/${issued.id}`);
    } catch (err) {
      setIssueError(err instanceof ApiError ? err.message : "Erro ao emitir o pré-laudo");
      setIssuing(false);
    }
  }

  async function savePatientCode() {
    if (!id) return;

    try {
      const res = await api.setPatientCode(id, codeDraft);
      if (res.data) setRadiograph(res.data);
      setEditingCode(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar o código do paciente");
    }
  }

  function isLit(classCode: string, index: number) {
    if (highlighted === null) return true;
    return highlighted.index !== null ? highlighted.index === index : highlighted.code === classCode;
  }

  const examImage = imageUrl && radiograph && (
    <div className="relative inline-block w-full">
      <img src={imageUrl} alt={radiograph.file_name} className="w-full rounded-md object-contain" />

      {showHeatmap && explanation && <Heatmap grid={explanation.grid} />}

      {/* Com o mapa de calor ligado, as caixas de achados saem para não poluir a leitura. */}
      {!showHeatmap &&
        findings.map((finding, i) =>
          decisionByIndex.get(i) === "discarded" ? null : (
          <div
            key={i}
            className="absolute rounded-sm border-2 transition-opacity"
            style={{
              borderStyle: decisionByIndex.has(i) ? "solid" : "dashed",
              left: `${finding.bbox.x * 100}%`,
              top: `${finding.bbox.y * 100}%`,
              width: `${finding.bbox.width * 100}%`,
              height: `${finding.bbox.height * 100}%`,
              borderColor: colorFor(finding.class_code),
              opacity: isLit(finding.class_code, i) ? 1 : 0.2
            }}
          >
            <span
              className="absolute -top-5 left-0 whitespace-nowrap rounded px-1 text-[10px] font-medium text-white"
              style={{ backgroundColor: colorFor(finding.class_code) }}
            >
              {finding.class_code}
            </span>
          </div>
          )
        )}
    </div>
  );

  if (loading) return <p className="text-sm text-slate-400">Carregando...</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!radiograph) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/radiografias" className="text-sm text-slate-500 hover:underline">
            &larr; Voltar
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">{radiograph.file_name}</h1>

          {editingCode ? (
            <div className="mt-1 flex items-center gap-2">
              <input
                autoFocus
                value={codeDraft}
                maxLength={60}
                onChange={(e) => setCodeDraft(e.target.value)}
                className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder="Nº do prontuário (sem nome ou CPF)"
              />
              <button onClick={savePatientCode} className="text-sm font-medium text-slate-700 underline">
                Salvar
              </button>
              <button onClick={() => setEditingCode(false)} className="text-sm text-slate-500 underline">
                Cancelar
              </button>
            </div>
          ) : (
            <p className="mt-0.5 text-sm text-slate-500">
              Código do paciente:{" "}
              <span className="font-medium text-slate-700">{radiograph.patient_code ?? "não informado"}</span>{" "}
              <button
                onClick={() => {
                  setCodeDraft(radiograph.patient_code ?? "");
                  setEditingCode(true);
                }}
                className="text-xs underline"
              >
                {radiograph.patient_code ? "alterar" : "informar"}
              </button>
            </p>
          )}
        </div>

        <button
          onClick={handleDelete}
          disabled={deleting}
          className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        >
          {deleting ? "Excluindo..." : "Excluir"}
        </button>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-4 xl:col-span-2">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-700">Exame</h2>
            <div className="flex gap-2">
              {explanation && (
                <button
                  onClick={() => setShowHeatmap((current) => !current)}
                  className={`rounded-md border px-3 py-1 text-xs font-medium ${
                    showHeatmap
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {showHeatmap ? "Ocultar mapa de calor" : "Por que a IA decidiu assim?"}
                </button>
              )}
              {imageUrl && (
                <button
                  onClick={() => setExpanded(true)}
                  className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Tela cheia
                </button>
              )}
            </div>
          </div>

          {imageUrl ? (
            <button onClick={() => setExpanded(true)} className="block w-full cursor-zoom-in" title="Ampliar">
              {examImage}
            </button>
          ) : (
            <p className="text-sm text-slate-400">Não foi possível gerar a pré-visualização da imagem.</p>
          )}

          {showHeatmap && explanation && (
            <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              As áreas em vermelho foram as que mais pesaram para a IA classificar esta imagem como{" "}
              <span className="font-medium">{explanation.target_class}</span>; as amarelas pesaram menos. É uma
              aproximação de baixa resolução do que influenciou o modelo, não a marcação de um defeito: use
              para conferir se a decisão se apoiou numa região que faz sentido.
            </p>
          )}

          {analysis && !explanation && (
            <p className="mt-3 text-xs text-slate-400">
              Esta análise é anterior ao mapa de calor. Clique em "Reanalisar" para gerá-lo.
            </p>
          )}

          <p className="mt-3 text-xs text-slate-400">
            {radiograph.file_type} · {(radiograph.file_size / 1024).toFixed(0)} KB
            {radiograph.created_at && ` · enviada em ${new Date(radiograph.created_at).toLocaleString("pt-BR")}`}
            {radiograph.exam_metadata?.source_format === "dicom" && " · recebida em DICOM e convertida para PNG"}
          </p>

          {radiograph.exam_metadata?.burned_in_annotation === true && (
            <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
              O arquivo DICOM indica que há texto gravado dentro da imagem (pode ser o nome do paciente). Confira a
              imagem e, se for o caso, desative essa opção no aparelho.
            </p>
          )}

          {radiograph.exam_metadata && (
            <details className="mt-2 text-xs text-slate-500">
              <summary className="cursor-pointer">Dados técnicos do exame (lidos do DICOM)</summary>
              <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1">
                {EXAM_METADATA_LABELS.filter(([key]) => radiograph.exam_metadata?.[key] !== undefined).map(([key, label]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <dt>{label}</dt>
                    <dd className="font-medium text-slate-600">{String(radiograph.exam_metadata?.[key])}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-slate-400">
                Dados do paciente não são lidos nem guardados, e o arquivo DICOM original não é armazenado.
              </p>
            </details>
          )}
        </div>

        <div className="space-y-4">
          {/* Etapa 1: a qualidade vem primeiro e decide se o pré-laudo é liberado. */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-700">1. Qualidade da imagem</h2>
                <p className="text-xs text-slate-400">A imagem está boa o suficiente para diagnóstico?</p>
              </div>
              {AI_ENABLED && (
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {analyzing ? "Analisando..." : analysis ? "Reanalisar" : "Analisar"}
                </button>
              )}
            </div>

            {analyzeError && <p className="text-sm text-red-600">{analyzeError}</p>}

            {!AI_ENABLED && !analysis && <p className="text-sm text-slate-400">Análise por IA em breve.</p>}

            {AI_ENABLED && !quality && !analyzeError && (
              <p className="text-sm text-slate-400">
                Exame ainda não analisado. Clique em "Analisar" para classificar a qualidade e gerar o pré-laudo.
              </p>
            )}

            {quality && (
              <>
                <div
                  className={`rounded-md border p-3 ${
                    quality.is_adequate ? "border-emerald-200 bg-emerald-50" : "border-red-300 bg-red-50"
                  }`}
                >
                  <p className={`text-lg font-semibold ${quality.is_adequate ? "text-emerald-800" : "text-red-800"}`}>
                    {quality.is_adequate ? "Adequada" : "Inadequada"}
                  </p>
                  <p className="text-sm text-slate-700">
                    Probabilidade de adequação: <span className="font-medium">{quality.score} / 100</span>
                  </p>
                  {!quality.is_adequate && (
                    <p className="mt-1 text-sm font-medium text-red-800">
                      Confira a imagem e refaça o exame enquanto o paciente está na clínica.
                    </p>
                  )}
                </div>

                <p className="mt-2 text-xs text-slate-400">
                  Triagem automática: acerta cerca de 78% das classificações e pode errar nos dois sentidos.
                </p>

                {quality.image_measurements && (
                  <details className="mt-2 text-xs text-slate-500">
                    <summary className="cursor-pointer">Medidas técnicas da imagem</summary>
                    <ul className="mt-2 space-y-1">
                      {quality.image_measurements.map((measurement) => (
                        <li key={measurement.key} className="flex justify-between">
                          <span>{measurement.label}</span>
                          <span className="font-medium text-slate-600">{measurement.value}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-slate-400">
                      Só informativas. Testadas contra imagens rotuladas, não se relacionaram com a adequação,
                      por isso não recebem nota nem entram no score.
                    </p>
                  </details>
                )}
              </>
            )}
          </div>

          <ReviewCard radiographId={radiograph.id} review={review} onSaved={setReview} />

          {/* Etapa 2: o pré-laudo só aparece depois da classificação de qualidade. */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-700">
              2. Pré-laudo{preReportOpen && findingsAvailable ? ` · ${detected.length} achado(s)` : ""}
            </h2>
            <p className="mb-3 text-xs text-slate-400">Achados detectados pela IA, marcados na própria imagem.</p>

            {!quality ? (
              <p className="text-sm text-slate-400">Disponível depois da classificação de qualidade (etapa 1).</p>
            ) : !findingsAvailable ? (
              <p className="text-sm text-slate-400">
                Esta radiografia ainda não foi avaliada quanto a achados clínicos. Clique em "Reanalisar".
              </p>
            ) : !preReportOpen ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                <p className="font-medium">Pré-laudo não liberado: a imagem foi classificada como inadequada.</p>
                <p className="mt-1">
                  Achados detectados numa imagem inadequada são pouco confiáveis. O indicado é refazer o exame.
                </p>
                <button onClick={() => setOpenAnyway(true)} className="mt-2 text-xs font-medium underline">
                  Ver o pré-laudo mesmo assim
                </button>
              </div>
            ) : (
              <>
                {!qualityOk && (
                  <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
                    Imagem classificada como inadequada: leia estes achados com cautela.
                  </p>
                )}

                {detected.length === 0 ? (
                  <p className="text-sm text-slate-400">Nenhum achado detectado nesta radiografia.</p>
                ) : (
                  <>
                  <p className="mb-2 text-xs text-slate-500">
                    {pendingCount === 0 ? (
                      <span className="font-medium text-emerald-700">Todos os achados foram validados.</span>
                    ) : (
                      <span>
                        <span className="font-medium text-slate-700">{pendingCount}</span> de {detected.length}{" "}
                        achado(s) aguardando a sua validação.
                      </span>
                    )}{" "}
                    Clique num tipo para confirmar ou descartar cada achado; na imagem, os pendentes ficam
                    tracejados e os descartados somem.
                  </p>
                  {validationError && <p className="mb-2 text-sm text-red-600">{validationError}</p>}
                  <ul className="space-y-2">
                    {groups.map((group) => (
                      <li key={group.code} className="rounded-md border border-slate-100">
                        <details>
                          <summary
                            onMouseEnter={() => setHighlighted({ code: group.code, index: null })}
                            onMouseLeave={() => setHighlighted(null)}
                            className="flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm hover:bg-slate-50"
                          >
                            <span className="flex flex-wrap items-center gap-2">
                              <span
                                className="h-2.5 w-2.5 shrink-0 rounded-full"
                                style={{ backgroundColor: colorFor(group.code) }}
                              />
                              <span className="font-medium">{group.label}</span>
                              <span className="text-slate-400">({group.code})</span>
                              {group.lowReliability && (
                                <span
                                  className="rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
                                  title="O modelo tem desempenho fraco nesta classe de achado."
                                >
                                  baixa confiabilidade
                                </span>
                              )}
                            </span>
                            <span className="flex shrink-0 items-center gap-2">
                              {group.items.some(({ index }) => !decisionByIndex.has(index)) && (
                                <button
                                  onClick={(e) => {
                                    e.preventDefault();
                                    void decide(
                                      group.items.filter(({ index }) => !decisionByIndex.has(index)).map(({ index }) => index),
                                      "confirmed"
                                    );
                                  }}
                                  className="rounded border border-emerald-300 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-50"
                                >
                                  Confirmar todos
                                </button>
                              )}
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                                {group.items.length}
                              </span>
                            </span>
                          </summary>

                          <ul className="border-t border-slate-100">
                            {group.items.map(({ finding, index }, position) => (
                              <li
                                key={index}
                                onMouseEnter={() => setHighlighted({ code: group.code, index })}
                                onMouseLeave={() => setHighlighted(null)}
                                className="flex items-center justify-between px-3 py-1.5 pl-8 text-sm text-slate-600 hover:bg-slate-50"
                              >
                                <span className={decisionByIndex.get(index) === "discarded" ? "text-slate-400 line-through" : ""}>
                                  {group.label} {position + 1}
                                  <span className="ml-2 text-xs text-slate-400">
                                    confiança {Math.round(finding.confidence * 100)}%
                                  </span>
                                </span>
                                <span className="flex gap-1">
                                  <button
                                    onClick={() => void decide([index], "confirmed")}
                                    className={`rounded border px-2 py-0.5 text-xs font-medium ${
                                      decisionByIndex.get(index) === "confirmed"
                                        ? "border-emerald-600 bg-emerald-600 text-white"
                                        : "border-slate-300 text-slate-600 hover:bg-emerald-50"
                                    }`}
                                  >
                                    Confirmar
                                  </button>
                                  <button
                                    onClick={() => void decide([index], "discarded")}
                                    className={`rounded border px-2 py-0.5 text-xs font-medium ${
                                      decisionByIndex.get(index) === "discarded"
                                        ? "border-red-600 bg-red-600 text-white"
                                        : "border-slate-300 text-slate-600 hover:bg-red-50"
                                    }`}
                                  >
                                    Descartar
                                  </button>
                                </span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      </li>
                    ))}
                  </ul>
                  </>
                )}

                <div className="mt-4 border-t border-slate-100 pt-3">
                  {!issueFormOpen ? (
                    <>
                      <button
                        onClick={() => setIssueFormOpen(true)}
                        disabled={pendingCount > 0}
                        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                      >
                        Emitir pré-laudo
                      </button>
                      <p className="mt-1 text-xs text-slate-500">
                        {pendingCount > 0
                          ? `Valide os ${pendingCount} achado(s) pendente(s) para poder emitir.`
                          : "Gera o documento no formato de laudo, só com os achados confirmados."}
                      </p>
                    </>
                  ) : (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void issuePreReport();
                      }}
                      className="space-y-3"
                    >
                      <p className="text-sm font-semibold text-slate-700">Dados do pré-laudo</p>
                      <p className="text-xs text-slate-500">
                        Só o tipo de exame é obrigatório. O que ficar em branco sai como "não informado", e a
                        impressão diagnóstica sai com linhas para preencher à mão.
                      </p>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">Formato do documento</label>
                        <select
                          value={issueFormat}
                          onChange={(e) => setIssueFormat(e.target.value as "esr" | "acr")}
                          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                        >
                          <option value="esr">ESR — Sociedade Europeia de Radiologia</option>
                          <option value="acr">ACR — Colégio Americano de Radiologia</option>
                        </select>
                        <p className="mt-1 text-[11px] text-slate-400">
                          O conteúdo é o mesmo; mudam a ordem e os títulos das seções. Dá para alternar depois, na
                          tela do documento.
                        </p>
                      </div>

                      {(
                        [
                          ["exam_type", "Tipo de exame", "Radiografia panorâmica", false],
                          ["requested_by", "Profissional solicitante", "Nome e CRO", false],
                          ["clinical_indication", "Indicação clínica", "Motivo do exame", true],
                          ["impression", "Impressão diagnóstica", "Sua interpretação do exame", true],
                          ["notes", "Recomendações e observações", "Condutas sugeridas, exames complementares", true]
                        ] as const
                      ).map(([field, label, placeholder, multiline]) => (
                        <div key={field}>
                          <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
                          {multiline ? (
                            <textarea
                              rows={2}
                              value={issueForm[field]}
                              placeholder={placeholder}
                              onChange={(e) => setIssueForm((current) => ({ ...current, [field]: e.target.value }))}
                              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                            />
                          ) : (
                            <input
                              required={field === "exam_type"}
                              value={issueForm[field]}
                              placeholder={placeholder}
                              onChange={(e) => setIssueForm((current) => ({ ...current, [field]: e.target.value }))}
                              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                            />
                          )}
                        </div>
                      ))}

                      <div className="flex gap-2">
                        <button
                          type="submit"
                          disabled={issuing}
                          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                        >
                          {issuing ? "Emitindo..." : "Emitir"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setIssueFormOpen(false)}
                          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
                        >
                          Cancelar
                        </button>
                      </div>
                    </form>
                  )}
                  {issueError && <p className="mt-1 text-sm text-red-600">{issueError}</p>}
                </div>

                <p className="mt-3 text-xs text-slate-400">
                  Ferramenta de apoio ao diagnóstico. Os resultados não substituem a avaliação de um
                  profissional habilitado.
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {preReports.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Pré-laudos emitidos ({preReports.length})</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {preReports.map((item) => (
              <li key={item.id} className="flex items-center justify-between py-2">
                <span className="text-slate-600">
                  {new Date(item.created_at).toLocaleString("pt-BR")} · por {item.issued_by_name ?? "—"}
                </span>
                <Link to={`/pre-laudos/${item.id}`} className="font-medium text-slate-700 hover:underline">
                  Abrir
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {expanded && imageUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setExpanded(false)}
        >
          <div className="relative max-h-full w-full max-w-[min(100%,170vh)]" onClick={(e) => e.stopPropagation()}>
            {examImage}
          </div>
          <button
            onClick={() => setExpanded(false)}
            className="absolute right-4 top-4 rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-800"
          >
            Fechar
          </button>
        </div>
      )}
    </div>
  );
}
