import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { AnalysisResult, QualityStatus, Radiograph } from "../lib/types";

const STATUS_STYLES: Record<QualityStatus, string> = {
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  attention: "bg-amber-50 text-amber-700 border-amber-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
  pending: "bg-slate-50 text-slate-500 border-slate-200"
};

const STATUS_LABELS: Record<QualityStatus, string> = {
  approved: "Aprovado",
  attention: "Atenção",
  rejected: "Reprovado",
  pending: "Pendente"
};

const BOX_COLORS = ["#f97316", "#3b82f6", "#a855f7", "#ef4444", "#10b981"];

export default function RadiographDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [radiograph, setRadiograph] = useState<Radiograph | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);

  function load() {
    if (!id) return;
    setLoading(true);
    setError(null);

    api
      .getRadiograph(id)
      .then((res) => {
        setRadiograph(res.data);
        setAnalysis(res.data.analysis_result ?? null);
        const url = res.signed_url?.signedUrl ?? res.signed_url?.signedURL ?? null;
        setImageUrl(url && url.startsWith("http") ? url : null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar radiografia"))
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  async function handleAnalyze() {
    if (!id) return;
    setAnalyzing(true);
    setAnalyzeError(null);

    try {
      const res = await api.analyzeRadiograph(id);
      setAnalysis(res.data);
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
        </div>

        <button
          onClick={handleDelete}
          disabled={deleting}
          className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        >
          {deleting ? "Excluindo..." : "Excluir"}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Imagem</h2>

          {imageUrl ? (
            <div className="relative inline-block w-full">
              <img src={imageUrl} alt={radiograph.file_name} className="w-full rounded-md object-contain" />

              {analysis?.yolo.findings.map((finding, i) => (
                <div
                  key={i}
                  className="absolute rounded-sm border-2 transition-opacity"
                  style={{
                    left: `${finding.bbox.x * 100}%`,
                    top: `${finding.bbox.y * 100}%`,
                    width: `${finding.bbox.width * 100}%`,
                    height: `${finding.bbox.height * 100}%`,
                    borderColor: BOX_COLORS[i % BOX_COLORS.length],
                    opacity: highlighted === null || highlighted === i ? 1 : 0.25
                  }}
                >
                  <span
                    className="absolute -top-5 left-0 whitespace-nowrap rounded px-1 text-[10px] font-medium text-white"
                    style={{ backgroundColor: BOX_COLORS[i % BOX_COLORS.length] }}
                  >
                    {finding.class_code}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Não foi possível gerar a pré-visualização da imagem.</p>
          )}

          <dl className="mt-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Tipo</dt>
              <dd>{radiograph.file_type}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Tamanho</dt>
              <dd>{(radiograph.file_size / 1024).toFixed(0)} KB</dd>
            </div>
            {radiograph.created_at && (
              <div className="flex justify-between">
                <dt className="text-slate-500">Enviada em</dt>
                <dd>{new Date(radiograph.created_at).toLocaleString("pt-BR")}</dd>
              </div>
            )}
          </dl>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-700">Análise de IA</h2>
                <p className="text-xs text-slate-400">Pré-laudo (achados clínicos) + controle de qualidade da imagem</p>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {analyzing ? "Analisando..." : analysis ? "Reanalisar" : "Analisar"}
              </button>
            </div>

            {analyzeError && <p className="text-sm text-red-600">{analyzeError}</p>}

            {!analysis && !analyzeError && (
              <p className="text-sm text-slate-400">
                Nenhuma análise realizada ainda. Clique em "Analisar" para rodar a detecção de
                achados (YOLOv8) e a checagem de adequação técnica.
              </p>
            )}
          </div>

          {analysis && (
            <>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700">Controle de qualidade da imagem</h3>
                    <p className="text-xs text-slate-400">
                      Métricas de imagem (nitidez, contraste, exposição) · a imagem está boa o suficiente para diagnóstico?
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      analysis.efficientnet.is_adequate
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-red-200 bg-red-50 text-red-700"
                    }`}
                  >
                    {analysis.efficientnet.is_adequate ? "Adequado" : "Não adequado"}
                  </span>
                </div>

                <div className="mb-3 flex items-end gap-1">
                  <span className="text-3xl font-semibold text-slate-900">{analysis.efficientnet.score}</span>
                  <span className="pb-1 text-sm text-slate-400">/ 100 índice técnico</span>
                </div>

                <ul className="space-y-1.5">
                  {analysis.efficientnet.criteria.map((criterion) => (
                    <li key={criterion.category} className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">
                        {criterion.label}
                        {criterion.raw_value != null && (
                          <span className="ml-1.5 text-xs text-slate-400">({criterion.raw_value})</span>
                        )}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[criterion.status]}`}
                      >
                        {STATUS_LABELS[criterion.status]}
                        {criterion.score != null ? ` · ${criterion.score}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>

                <p className="mt-3 text-sm text-slate-600">{analysis.efficientnet.recommendation}</p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-slate-700">
                  Pré-laudo · achados clínicos ({analysis.yolo.findings.length})
                </h3>
                <p className="mb-3 text-xs text-slate-400">YOLOv8 · o que foi encontrado e onde, na própria imagem</p>

                {analysis.yolo.findings.length === 0 ? (
                  <p className="text-sm text-slate-400">Nenhum achado detectado nesta radiografia.</p>
                ) : (
                  <ul className="space-y-2">
                    {analysis.yolo.findings.map((finding, i) => (
                      <li
                        key={i}
                        onMouseEnter={() => setHighlighted(i)}
                        onMouseLeave={() => setHighlighted(null)}
                        className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm hover:bg-slate-50"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: BOX_COLORS[i % BOX_COLORS.length] }}
                          />
                          <span className="font-medium">{finding.label}</span>
                          <span className="text-slate-400">({finding.class_code})</span>
                        </div>
                        <span className="text-slate-500">{Math.round(finding.confidence * 100)}%</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <p className="text-xs text-slate-400">
                Ferramenta de apoio ao diagnóstico. Os resultados não substituem a avaliação de um
                profissional habilitado.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
