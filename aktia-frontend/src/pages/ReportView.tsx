import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { PeriodSummary, QualityReport } from "../lib/types";
import { formatPeriod } from "./Reports";

// O relatório mostra exatamente o que foi gravado na emissão (report.data).
// Nada aqui é recalculado: só formatação.
export default function ReportView() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getQualityReport(id)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar relatório"));
  }, [id]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!report) return <p className="text-sm text-slate-400">Carregando...</p>;

  const { data } = report;
  const insufficient = `dados insuficientes (mínimo de ${data.min_sample_size} análises)`;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between print:hidden">
        <Link to="/relatorios" className="text-sm text-slate-500 hover:underline">
          &larr; Relatórios
        </Link>
        <button
          onClick={() => window.print()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Imprimir / salvar em PDF
        </button>
      </div>

      <article className="space-y-6 rounded-lg border border-slate-200 bg-white p-8 print:border-0 print:p-0">
        <header className="border-b border-slate-200 pb-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">AktIA</p>
          <h1 className="text-xl font-semibold text-slate-900">Relatório de Garantia da Qualidade</h1>
          <p className="text-sm text-slate-500">Avaliação da qualidade técnica das radiografias</p>

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Serviço">{data.clinic.name}</Field>
            <Field label="CNPJ">{data.clinic.cnpj ?? "—"}</Field>
            <Field label="Período">{formatPeriod(data.period.start, data.period.end)}</Field>
            <Field label="Emitido em">{new Date(report.created_at).toLocaleString("pt-BR")}</Field>
            <Field label="Emitido por">{data.generated_by.full_name ?? "—"}</Field>
            <Field label="Identificador">{report.id}</Field>
          </dl>
        </header>

        <Section title="1. Volume de exames">
          <Table
            head={["Radiografias enviadas", "Analisadas", "Sem análise"]}
            rows={[[data.volume.uploaded, data.volume.analyzed, data.volume.not_analyzed]]}
          />
        </Section>

        <Section title="2. Indicadores de qualidade">
          <Table
            head={["", "Período", "Período anterior"]}
            rows={[
              ["Análises", data.summary.total, data.previous.total],
              ["Adequadas", count(data.summary, "approved"), count(data.previous, "approved")],
              ["Inadequadas", count(data.summary, "rejected"), count(data.previous, "rejected")],
              ["Taxa de inadequadas", rate(data.summary), rate(data.previous)],
              ["Score médio (0–100)", score(data.summary), score(data.previous)]
            ]}
          />
          <p className="mt-2 text-xs text-slate-500">
            Período anterior: {formatPeriod(data.previous_period.start, data.previous_period.end)}.{" "}
            {data.comparison.insufficient_data
              ? `Comparação indisponível: ${insufficient} em um dos períodos.`
              : `Variação do score médio: ${signed(data.comparison.avg_score_delta)} ponto(s); variação da taxa de adequadas: ${signed(
                  data.comparison.approved_rate_delta
                )} ponto(s) percentual(is).`}
          </p>
        </Section>

        <Section title={`3. Evolução no período (por ${data.history_granularity === "week" ? "semana" : "dia"})`}>
          {data.history ? (
            <Table
              head={[data.history_granularity === "week" ? "Semana iniciada em" : "Dia", "Análises", "Score médio"]}
              rows={data.history.map((point) => [
                point.bucket.split("-").reverse().join("/"),
                point.total,
                point.avg_score != null ? point.avg_score.toFixed(1) : "—"
              ])}
            />
          ) : (
            <Note>Evolução não apresentada: {insufficient}.</Note>
          )}
        </Section>

        <Section title="4. Qualidade por profissional responsável pela captura">
          {data.professionals.length === 0 ? (
            <Note>Nenhum profissional cadastrado.</Note>
          ) : (
            <Table
              head={["Profissional", "Análises", "Adequadas", "Taxa de adequadas", "Score médio"]}
              rows={data.professionals.map((p) => [
                p.full_name ?? "Sem profissional informado",
                p.total,
                p.status_counts.approved,
                p.approved_rate != null ? `${p.approved_rate.toFixed(1)}%` : p.total === 0 ? "—" : "dados insuficientes",
                p.avg_score != null ? p.avg_score.toFixed(1) : p.total === 0 ? "—" : "dados insuficientes"
              ])}
            />
          )}
        </Section>

        <Section title="5. Problemas de imagem mais frequentes">
          {data.quality_findings === null ? (
            <Note>Não apresentado: {insufficient}.</Note>
          ) : data.quality_findings.length === 0 ? (
            <Note>Nenhum critério de imagem em atenção ou reprovado no período.</Note>
          ) : (
            <Table
              head={["Critério", "Ocorrências", "Participação"]}
              rows={data.quality_findings.map((f) => [f.label, f.count, `${f.percentage.toFixed(1)}%`])}
            />
          )}
        </Section>

        <Section title="6. Ações corretivas e observações">
          {report.notes ? (
            <p className="whitespace-pre-wrap text-sm text-slate-700">{report.notes}</p>
          ) : (
            <Note>Nenhuma observação registrada na emissão.</Note>
          )}
        </Section>

        <Section title="7. Metodologia e limitações">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
            {data.methodology.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-slate-700">
            Modelo(s) utilizado(s) nas análises do período:{" "}
            {data.models.length > 0
              ? data.models.map((m) => `${m.model_version} (${m.total} análise(s))`).join("; ")
              : "nenhuma análise no período"}
            .
          </p>
        </Section>

        <footer className="grid grid-cols-2 gap-10 pt-10 text-center text-xs text-slate-500">
          <div className="border-t border-slate-400 pt-2">Responsável técnico</div>
          <div className="border-t border-slate-400 pt-2">Responsável legal</div>
        </footer>
      </article>
    </div>
  );
}

function count(summary: PeriodSummary, key: "approved" | "rejected") {
  return summary.status_counts[key];
}

function rate(summary: PeriodSummary) {
  return summary.status_rates ? `${summary.status_rates.rejected.toFixed(1)}%` : "dados insuficientes";
}

function score(summary: PeriodSummary) {
  return summary.avg_score != null ? summary.avg_score.toFixed(1) : "dados insuficientes";
}

function signed(value: number | null) {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="break-all font-medium text-slate-800">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="break-inside-avoid">
      <h2 className="mb-2 text-sm font-semibold text-slate-800">{title}</h2>
      {children}
    </section>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-500">{children}</p>;
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr>
          {head.map((cell, i) => (
            <th key={i} className="border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs font-medium text-slate-500">
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j} className="border border-slate-200 px-3 py-1.5 text-slate-700">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
