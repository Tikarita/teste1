import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { PreReport } from "../lib/types";

// O documento mostra exatamente o que foi gravado na emissão (report.data).
// A imagem vem do exame: se a radiografia for excluída, o pré-laudo continua
// com os achados, mas sem a figura.
export default function PreReportView() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<PreReport | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    api
      .getPreReport(id)
      .then((loaded) => {
        setReport(loaded);
        if (!loaded.radiograph_id) return;

        api
          .getRadiograph(loaded.radiograph_id)
          .then((res) => {
            const url = res.signed_url?.signedUrl ?? res.signed_url?.signedURL ?? null;
            setImageUrl(url && url.startsWith("http") ? url : null);
          })
          .catch(() => setImageUrl(null));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar o pré-laudo"));
  }, [id]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!report) return <p className="text-sm text-slate-400">Carregando...</p>;

  const { data } = report;
  const quality = data.quality;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between print:hidden">
        <Link
          to={report.radiograph_id ? `/radiografias/${report.radiograph_id}` : "/radiografias"}
          className="text-sm text-slate-500 hover:underline"
        >
          &larr; Exame
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
          <h1 className="text-xl font-semibold text-slate-900">Pré-laudo radiográfico</h1>
          <p className="text-sm text-slate-500">Documento de apoio ao diagnóstico — não é laudo</p>

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Serviço">{data.clinic.name}</Field>
            <Field label="CNPJ">{data.clinic.cnpj ?? "—"}</Field>
            <Field label="Código do paciente">{data.exam.patient_code ?? "não informado"}</Field>
            <Field label="Arquivo do exame">{data.exam.file_name}</Field>
            <Field label="Exame enviado em">{new Date(data.exam.uploaded_at).toLocaleString("pt-BR")}</Field>
            <Field label="Responsável pela captura">{data.exam.professional_name ?? "não informado"}</Field>
            <Field label="Pré-laudo emitido por">{data.issued_by.full_name ?? "—"}</Field>
            <Field label="Emitido em">{new Date(report.created_at).toLocaleString("pt-BR")}</Field>
            <Field label="Identificador">{report.id}</Field>
          </dl>
        </header>

        <Section title="1. Qualidade da imagem">
          <p className="text-sm text-slate-700">
            Classificação automática:{" "}
            <span className="font-medium">
              {quality.ai_is_adequate === null ? "não disponível" : quality.ai_is_adequate ? "adequada" : "inadequada"}
            </span>
            {quality.ai_score !== null && ` (probabilidade de adequação: ${quality.ai_score} / 100)`}.
          </p>
          <p className="text-sm text-slate-700">
            Revisão do profissional:{" "}
            <span className="font-medium">
              {quality.review_verdict === null
                ? "não registrada"
                : quality.review_verdict === "adequate"
                ? "adequada"
                : "inadequada"}
            </span>
            {quality.review_by && ` (por ${quality.review_by})`}.
          </p>
          {(quality.review_verdict === "inadequate" ||
            (quality.review_verdict === null && quality.ai_is_adequate === false)) && (
            <p className="mt-1 text-sm font-medium text-slate-900">
              Atenção: imagem considerada inadequada. Os achados abaixo devem ser lidos com cautela.
            </p>
          )}
        </Section>

        <Section title="2. Imagem com os achados confirmados">
          {imageUrl ? (
            <div className="relative inline-block w-full">
              <img src={imageUrl} alt={data.exam.file_name} className="w-full rounded-md" />
              {data.findings.map((finding) => (
                <div
                  key={finding.number}
                  className="absolute border-2 border-slate-900"
                  style={{
                    left: `${finding.bbox.x * 100}%`,
                    top: `${finding.bbox.y * 100}%`,
                    width: `${finding.bbox.width * 100}%`,
                    height: `${finding.bbox.height * 100}%`,
                    borderColor: "#facc15"
                  }}
                >
                  <span
                    className="absolute -left-0.5 -top-5 rounded px-1 text-[11px] font-bold"
                    style={{ backgroundColor: "#facc15", color: "#0f172a", printColorAdjust: "exact" }}
                  >
                    {finding.number}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <Note>A imagem deste exame não está mais disponível.</Note>
          )}
        </Section>

        <Section title={`3. Achados confirmados (${data.findings.length})`}>
          {data.findings.length === 0 ? (
            <Note>Nenhum achado confirmado pelo profissional neste exame.</Note>
          ) : (
            <>
              <Table
                head={["Tipo de achado", "Quantidade", "Números na imagem"]}
                rows={data.groups.map((group) => [
                  `${group.label} (${group.class_code})`,
                  group.count,
                  group.numbers.join(", ")
                ])}
              />
              <div className="mt-3">
                <Table
                  head={["Nº", "Achado", "Confiança da IA", "Confirmado por"]}
                  rows={data.findings.map((finding) => [
                    finding.number,
                    finding.label + (finding.low_reliability ? " *" : ""),
                    `${Math.round(finding.confidence * 100)}%`,
                    finding.validated_by_name ?? "—"
                  ])}
                />
              </div>
              {data.findings.some((finding) => finding.low_reliability) && (
                <p className="mt-2 text-xs text-slate-500">
                  * Tipo de achado em que o modelo tem desempenho fraco.
                </p>
              )}
            </>
          )}
          <p className="mt-2 text-xs text-slate-500">
            A IA sugeriu {data.detected_count} achado(s); o profissional descartou {data.discarded_count}.
          </p>
        </Section>

        <Section title="4. Observações">
          {report.notes ? (
            <p className="whitespace-pre-wrap text-sm text-slate-700">{report.notes}</p>
          ) : (
            <Note>Nenhuma observação registrada na emissão.</Note>
          )}
        </Section>

        <Section title="5. Avisos">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
            {data.disclaimer.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-500">
            Modelos: qualidade {quality.model_version ?? "não informado"}; detecção{" "}
            {data.detector_model ?? "não informado"}.
          </p>
        </Section>

        <footer className="pt-10 text-center text-xs text-slate-500">
          <div className="mx-auto w-1/2 border-t border-slate-400 pt-2">Cirurgião-dentista responsável (nome e CRO)</div>
        </footer>
      </article>
    </div>
  );
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
