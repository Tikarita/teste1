import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useClinics } from "../context/ClinicContext";
import type {
  ClinicalFindingsStats,
  DetectorStats,
  QualityHistory,
  QualitySummary,
  Radiograph,
  ReviewStatsResponse,
  StatsPeriod
} from "../lib/types";

type ApiStatus = "checking" | "online" | "offline";

const PERIODS: { value: StatsPeriod; label: string }[] = [
  { value: "7", label: "7 dias" },
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" }
];

// Todos os números desta tela vêm prontos do backend (/stats/*). Aqui só há
// formatação: nada de média, taxa ou contagem calculada no navegador.
export default function Dashboard() {
  const { clinics, selectedClinicId } = useClinics();
  const activeClinic = clinics.find((c) => c.id === selectedClinicId) ?? null;

  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [dbStatus, setDbStatus] = useState<ApiStatus>("checking");

  const [period, setPeriod] = useState<StatsPeriod>("30");
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [history, setHistory] = useState<QualityHistory | null>(null);
  const [clinicalFindings, setClinicalFindings] = useState<ClinicalFindingsStats | null>(null);
  const [reviews, setReviews] = useState<ReviewStatsResponse | null>(null);
  const [detector, setDetector] = useState<DetectorStats | null>(null);
  const [recent, setRecent] = useState<Radiograph[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(() => setApiStatus("online")).catch(() => setApiStatus("offline"));
    api.databaseTest().then(() => setDbStatus("online")).catch(() => setDbStatus("offline"));
  }, []);

  useEffect(() => {
    if (!selectedClinicId) {
      setRecent([]);
      return;
    }

    // A lista já vem do backend em ordem do mais recente para o mais antigo.
    api
      .listRadiographsByClinic(selectedClinicId)
      .then((res) => setRecent(res.data.slice(0, 6)))
      .catch(() => setRecent([]));
  }, [selectedClinicId]);

  useEffect(() => {
    if (!selectedClinicId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setStatsError(null);

    // Cada painel falha sozinho: um erro numa estatística não apaga as outras.
    const orNull = (err: unknown) => {
      setStatsError(err instanceof Error ? err.message : "Erro ao carregar estatísticas");
      return null;
    };

    Promise.all([
      api.statsSummary({ period }).catch(orNull),
      api.statsHistory({ period }).catch(orNull),
      api.statsClinicalFindings({ period }).catch(orNull),
      api.statsReviews({ period }).catch(orNull),
      api.statsDetector({ period }).catch(orNull)
    ])
      .then(([summaryData, historyData, clinicalData, reviewData, detectorData]) => {
        setDetector(detectorData);
        setReviews(reviewData);
        setSummary(summaryData);
        setHistory(historyData);
        setClinicalFindings(clinicalData);
      })
      .finally(() => setLoading(false));
  }, [selectedClinicId, period]);

  const current = summary?.current ?? null;
  const delta = summary?.comparison.avg_score_delta ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {activeClinic ? activeClinic.name : "Dashboard"}
          </h1>
          <p className="text-sm text-slate-500">Qualidade das radiografias analisadas no período.</p>
        </div>

        <div className="flex rounded-md border border-slate-200 bg-white p-0.5 text-sm">
          {PERIODS.map((option) => (
            <button
              key={option.value}
              onClick={() => setPeriod(option.value)}
              className={`rounded px-3 py-1 ${
                period === option.value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {statsError && <p className="text-sm text-red-600">{statsError}</p>}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Análises no período" value={current ? String(current.total) : "—"} />
        <StatCard
          label="Score médio"
          value={current?.avg_score != null ? current.avg_score.toFixed(1) : "—"}
          hint={
            !current
              ? undefined
              : current.insufficient_data
              ? `Dados insuficientes (mínimo de ${summary?.min_sample_size} análises)`
              : delta != null
              ? `${delta > 0 ? "+" : ""}${delta.toFixed(1)} em relação ao período anterior`
              : "Sem período anterior para comparar"
          }
        />
        <StatCard
          label="Adequadas"
          value={current ? String(current.status_counts.approved) : "—"}
          hint={current?.status_rates ? `${current.status_rates.approved.toFixed(1)}% das análises` : undefined}
          tone="good"
        />
        <StatCard
          label="Inadequadas"
          value={current ? String(current.status_counts.rejected) : "—"}
          hint={current?.status_rates ? `${current.status_rates.rejected.toFixed(1)}% das análises` : undefined}
          tone="warn"
        />
      </div>

      <Panel
        title="Revisão pelos profissionais"
        subtitle="Decisão humana sobre os exames enviados no período. É a taxa de rejeição que vai para o relatório."
      >
        {loading && <Muted>Carregando...</Muted>}
        {!loading && reviews && (
          <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <Metric
              label="Exames revisados"
              value={`${reviews.reviewed} de ${reviews.uploaded}`}
              hint={reviews.coverage_rate != null ? `${reviews.coverage_rate.toFixed(1)}% de cobertura` : undefined}
            />
            <Metric
              label="Taxa de rejeição"
              value={reviews.rejection_rate != null ? `${reviews.rejection_rate.toFixed(1)}%` : "—"}
              hint={
                reviews.insufficient_data
                  ? `Dados insuficientes (mínimo de ${reviews.min_sample_size} revisões)`
                  : `${reviews.human_inadequate} exame(s) inadequado(s)`
              }
            />
            <Metric
              label="Exames repetidos"
              value={String(reviews.repeated)}
              hint={reviews.repeat_rate != null ? `${reviews.repeat_rate.toFixed(1)}% dos revisados` : undefined}
            />
            <Metric
              label="Concordância com a IA"
              value={reviews.ai_agreement_rate != null ? `${reviews.ai_agreement_rate.toFixed(1)}%` : "—"}
              hint={
                reviews.compared_with_ai > 0
                  ? `IA deixou passar ${reviews.ai_missed}; alarme falso em ${reviews.ai_false_alarm}`
                  : "Nenhum exame revisado tem análise da IA"
              }
            />
          </div>
        )}
        {!loading && reviews?.reasons && reviews.reasons.length > 0 && (
          <p className="mt-3 text-xs text-slate-500">
            Motivos de rejeição:{" "}
            {reviews.reasons.map((r) => `${r.label} (${r.count})`).join(", ")}
          </p>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Score médio ao longo do tempo"
          subtitle={history ? (history.granularity === "week" ? "Por semana" : "Por dia") : undefined}
        >
          {loading && <Muted>Carregando...</Muted>}
          {!loading && history?.insufficient_data && <Insufficient min={history.min_sample_size} />}
          {!loading && history?.points && (
            <ul className="space-y-1.5">
              {history.points.map((point) => (
                <li key={point.bucket} className="flex items-center gap-3 text-sm">
                  <span className="w-20 shrink-0 text-slate-500">{formatDay(point.bucket)}</span>
                  <Bar percent={point.avg_score ?? 0} />
                  <span className="w-24 shrink-0 text-right text-slate-700">
                    {point.avg_score != null ? point.avg_score.toFixed(1) : "—"}
                    <span className="ml-1 text-xs text-slate-400">({point.total})</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Exames recentes">
          {recent.length === 0 && <Muted>Nenhum exame enviado ainda nesta clínica.</Muted>}

          {recent.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {recent.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <Link to={`/radiografias/${r.id}`} className="font-medium text-slate-700 hover:underline">
                    {r.file_name}
                  </Link>
                  {r.analysis_result ? (
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        r.analysis_result.efficientnet.is_adequate
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-red-200 bg-red-50 text-red-700"
                      }`}
                    >
                      {r.analysis_result.efficientnet.is_adequate ? "Adequado" : "Inadequado"}
                    </span>
                  ) : (
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
                      Não analisado
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Achados clínicos mais frequentes"
          subtitle={
            clinicalFindings
              ? `Detector de achados · ${clinicalFindings.analyses_evaluated} análise(s) avaliada(s) no período`
              : undefined
          }
        >
          {loading && <Muted>Carregando...</Muted>}
          {!loading && clinicalFindings?.insufficient_data && (
            <Insufficient min={clinicalFindings.min_sample_size} what="análises com detecção de achados" />
          )}
          {!loading && clinicalFindings?.items?.length === 0 && (
            <Muted>Nenhum achado detectado nas análises do período.</Muted>
          )}
          {!loading && clinicalFindings?.items && clinicalFindings.items.length > 0 && (
            <ul className="space-y-2">
              {clinicalFindings.items.slice(0, 6).map((item) => (
                <li key={item.class_code} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    {item.label} <span className="text-slate-400">({item.class_code})</span>
                    {item.low_reliability && (
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                        baixa confiabilidade
                      </span>
                    )}
                  </span>
                  <span className="text-slate-700">
                    {item.count}
                    <span className="ml-1 text-xs text-slate-400">
                      em {item.percentage_of_analyses.toFixed(1)}% das análises
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Acerto do detector de achados"
        subtitle="Dos achados que os profissionais validaram no pré-laudo, quantos foram confirmados."
      >
        {loading && <Muted>Carregando...</Muted>}
        {!loading && detector && detector.validated === 0 && (
          <Muted>Nenhum achado validado no período. A validação é feita na tela de cada exame.</Muted>
        )}
        {!loading && detector && detector.validated > 0 && (
          <>
            <p className="mb-3 text-sm text-slate-600">
              {detector.confirmation_rate != null ? (
                <>
                  <span className="text-lg font-semibold text-slate-900">{detector.confirmation_rate.toFixed(1)}%</span>{" "}
                  dos {detector.validated} achados validados foram confirmados.
                </>
              ) : (
                `${detector.validated} achado(s) validado(s); mínimo de ${detector.min_sample_size} para calcular a taxa.`
              )}
            </p>
            <ul className="space-y-1.5">
              {detector.classes.map((item) => (
                <li key={item.class_code} className="flex items-center gap-3 text-sm">
                  <span className="w-56 shrink-0 truncate text-slate-600">
                    {item.label} <span className="text-slate-400">({item.class_code})</span>
                  </span>
                  <Bar percent={item.confirmation_rate ?? 0} />
                  <span className="w-44 shrink-0 text-right text-slate-700">
                    {item.confirmation_rate != null ? `${item.confirmation_rate.toFixed(1)}%` : "dados insuficientes"}
                    <span className="ml-1 text-xs text-slate-400">
                      ({item.confirmed} de {item.validated})
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Panel>

      <div className="flex gap-4 text-xs text-slate-400">
        <span>API: {apiStatus === "checking" ? "verificando..." : apiStatus === "online" ? "online" : "offline"}</span>
        <span>Banco: {dbStatus === "checking" ? "verificando..." : dbStatus === "online" ? "online" : "offline"}</span>
      </div>
    </div>
  );
}

function formatDay(isoDate: string) {
  const [, month, day] = isoDate.split("-");
  return `${day}/${month}`;
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-slate-900">{value}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-400">{children}</p>;
}

function Insufficient({ min, what = "análises" }: { min: number; what?: string }) {
  return (
    <Muted>
      Dados insuficientes: são necessárias pelo menos {min} {what} no período.
    </Muted>
  );
}

function Bar({ percent }: { percent: number }) {
  return (
    <div className="h-2 flex-1 rounded-full bg-slate-100">
      <div className="h-2 rounded-full bg-slate-700" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "good" | "warn";
}) {
  const toneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50"
      : "border-slate-200 bg-white";

  return (
    <div className={`rounded-lg border p-4 ${toneClass}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
