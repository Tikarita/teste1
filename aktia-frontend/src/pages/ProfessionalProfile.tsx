import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { PeriodSummary, ProfessionalProfile as Profile, StatsPeriod } from "../lib/types";

const PERIODS: { value: StatsPeriod; label: string }[] = [
  { value: "7", label: "7 dias" },
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" }
];

// Todos os números vêm prontos do backend (/stats/professionals/{id}),
// inclusive as diferenças em relação à clínica e ao período anterior.
export default function ProfessionalProfile() {
  const { id } = useParams<{ id: string }>();
  const [period, setPeriod] = useState<StatsPeriod>("90");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setError(null);
    api
      .statsProfessionalProfile(id, { period })
      .then(setProfile)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar o perfil"))
      .finally(() => setLoading(false));
  }, [id, period]);

  if (error) {
    return (
      <div className="space-y-3">
        <Link to="/clinica" className="text-sm text-slate-500 hover:underline">
          &larr; Clínica
        </Link>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!profile) return <p className="text-sm text-slate-400">Carregando...</p>;

  const { summary, clinic_summary: clinic, versus_clinic: versus, comparison, review } = profile;
  const insufficient = `Dados insuficientes (mínimo de ${profile.min_sample_size} análises)`;

  return (
    <div className={`space-y-6 ${loading ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/clinica" className="text-sm text-slate-500 hover:underline">
            &larr; Clínica
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">
            {profile.professional.full_name ?? "Profissional"}
          </h1>
          <p className="text-sm text-slate-500">
            Qualidade das radiografias em que este profissional foi o responsável pela captura.
          </p>
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

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Análises no período" value={String(summary.total)} hint={`Clínica: ${clinic.total}`} />
        <Card
          label="Score médio"
          value={summary.avg_score != null ? summary.avg_score.toFixed(1) : "—"}
          hint={
            summary.insufficient_data
              ? insufficient
              : versus.avg_score_delta != null
              ? `${signed(versus.avg_score_delta)} em relação à clínica (${score(clinic)})`
              : "Clínica sem dados suficientes para comparar"
          }
        />
        <Card
          label="Adequadas (IA)"
          value={summary.status_rates ? `${summary.status_rates.approved.toFixed(1)}%` : "—"}
          hint={
            summary.insufficient_data
              ? `${summary.status_counts.approved} de ${summary.total}`
              : versus.approved_rate_delta != null
              ? `${signed(versus.approved_rate_delta)} p.p. em relação à clínica`
              : `${summary.status_counts.approved} de ${summary.total}`
          }
        />
        <Card
          label="Taxa de rejeição (revisão)"
          value={review.rejection_rate != null ? `${review.rejection_rate.toFixed(1)}%` : "—"}
          hint={
            review.insufficient_data
              ? `${review.reviewed} de ${review.uploaded} exames revisados; mínimo de ${profile.min_sample_size}`
              : profile.clinic_rejection_rate != null
              ? `Clínica: ${profile.clinic_rejection_rate.toFixed(1)}% · ${review.reviewed} de ${review.uploaded} revisados`
              : `${review.reviewed} de ${review.uploaded} revisados`
          }
        />
      </div>

      <p className="text-xs text-slate-500">
        {comparison.insufficient_data
          ? "Sem comparação com o período anterior: um dos dois períodos não tem dados suficientes."
          : `Em relação ao período anterior: score médio ${signed(comparison.avg_score_delta)} ponto(s), taxa de adequadas ${signed(
              comparison.approved_rate_delta
            )} p.p.`}
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Score médio ao longo do tempo"
          subtitle={profile.history_granularity === "week" ? "Por semana" : "Por dia"}
        >
          {profile.history ? (
            <ul className="space-y-1.5">
              {profile.history.map((point) => (
                <li key={point.bucket} className="flex items-center gap-3 text-sm">
                  <span className="w-20 shrink-0 text-slate-500">{point.bucket.split("-").reverse().slice(0, 2).join("/")}</span>
                  <Bar percent={point.avg_score ?? 0} />
                  <span className="w-24 shrink-0 text-right text-slate-700">
                    {point.avg_score != null ? point.avg_score.toFixed(1) : "—"}
                    <span className="ml-1 text-xs text-slate-400">({point.total})</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Muted>{insufficient}.</Muted>
          )}
        </Panel>

        <Panel title="Motivos de rejeição" subtitle="Apontados na revisão humana dos exames deste profissional.">
          {review.reasons === null ? (
            <Muted>
              Dados insuficientes: são necessárias pelo menos {profile.min_sample_size} revisões no período.
            </Muted>
          ) : review.reasons.length === 0 ? (
            <Muted>Nenhum exame rejeitado na revisão.</Muted>
          ) : (
            <Shares items={review.reasons.map((r) => ({ key: r.reason, label: r.label, count: r.count, percentage: r.percentage }))} />
          )}
          {review.repeated > 0 && (
            <p className="mt-3 text-xs text-slate-500">{review.repeated} exame(s) precisaram ser repetidos.</p>
          )}
        </Panel>

        <Panel title="Como ler estes números">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-600">
            <li>
              O score e a taxa de adequadas vêm da triagem da IA, que acerta cerca de 78% das classificações e
              deixa passar parte das imagens ruins. Diferenças pequenas entre profissionais não são conclusivas.
            </li>
            <li>A taxa de rejeição vem da revisão humana e considera só os exames já revisados.</li>
            <li>Médias e taxas só aparecem a partir de {profile.min_sample_size} análises ou revisões no período.</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function score(summary: PeriodSummary) {
  return summary.avg_score != null ? summary.avg_score.toFixed(1) : "—";
}

function signed(value: number | null) {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function Shares({ items }: { items: { key: string; label: string; count: number; percentage: number }[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item.key} className="flex items-center gap-3 text-sm">
          <span className="w-40 shrink-0 truncate text-slate-600">{item.label}</span>
          <Bar percent={item.percentage} />
          <span className="w-24 shrink-0 text-right text-slate-700">
            {item.percentage.toFixed(1)}%<span className="ml-1 text-xs text-slate-400">({item.count})</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function Bar({ percent }: { percent: number }) {
  return (
    <div className="h-2 flex-1 rounded-full bg-slate-100">
      <div className="h-2 rounded-full bg-slate-700" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
    </div>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-400">{children}</p>;
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

function Card({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
