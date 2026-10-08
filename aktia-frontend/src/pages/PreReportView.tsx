import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { PreReport } from "../lib/types";

// Garante que os fundos (marcadores na imagem, cabeçalho da tabela) saiam na impressão.
const PRINT_COLORS: CSSProperties = { printColorAdjust: "exact", WebkitPrintColorAdjust: "exact" };

// Uma cor só para todas as marcações: o documento é lido pelos números.
const MARKER = "#facc15";

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
  const { quality } = data;

  // A revisão do profissional, quando existe, é a que vale para o documento.
  const adequate = quality.review_verdict !== null ? quality.review_verdict === "adequate" : quality.ai_is_adequate;
  const qualitySource =
    quality.review_verdict !== null
      ? `avaliação do profissional${quality.review_by ? ` (${quality.review_by})` : ""}`
      : "classificação automática";

  const validators = [...new Set(data.findings.map((f) => f.validated_by_name).filter(Boolean))].join(", ");
  const hasFlagged = data.findings.some((f) => f.low_reliability);

  return (
    <div className="mx-auto max-w-[210mm] space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <Link
          to={report.radiograph_id ? `/radiografias/${report.radiograph_id}` : "/radiografias"}
          className="text-sm text-slate-500 hover:underline"
        >
          &larr; Voltar ao exame
        </Link>
        <button
          onClick={() => window.print()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Imprimir / salvar em PDF
        </button>
      </div>

      <article className="bg-white px-12 py-10 text-[13px] leading-relaxed text-slate-800 shadow-sm ring-1 ring-slate-200 print:p-0 print:shadow-none print:ring-0">
        {/* Cabeçalho: quem emite e que documento é */}
        <header className="flex items-end justify-between gap-6 border-b-2 border-slate-800 pb-3">
          <div>
            <p className="text-lg font-semibold text-slate-900">{data.clinic.name}</p>
            {data.clinic.cnpj && <p className="text-xs text-slate-500">CNPJ {data.clinic.cnpj}</p>}
          </div>
          <div className="text-right">
            <p className="text-lg font-semibold tracking-wide text-slate-900">PRÉ-LAUDO RADIOGRÁFICO</p>
            <p className="text-xs text-slate-500">
              Nº {report.id.slice(0, 8).toUpperCase()} · emitido em {new Date(report.created_at).toLocaleDateString("pt-BR")}
            </p>
          </div>
        </header>

        {/* Identificação do exame */}
        <table className="mt-4 w-full border-collapse">
          <tbody>
            <tr>
              <InfoCell label="Paciente (código)">{data.exam.patient_code ?? "Não informado"}</InfoCell>
              <InfoCell label="Data do exame">{new Date(data.exam.uploaded_at).toLocaleDateString("pt-BR")}</InfoCell>
            </tr>
            <tr>
              <InfoCell label="Exame realizado por">{data.exam.professional_name ?? "Não informado"}</InfoCell>
              <InfoCell label="Pré-laudo emitido por">{data.issued_by.full_name ?? "—"}</InfoCell>
            </tr>
          </tbody>
        </table>

        <Section title="Qualidade da imagem">
          <p>
            {adequate === null ? (
              "Qualidade não avaliada."
            ) : adequate ? (
              <>
                <strong>Adequada</strong> para avaliação, segundo a {qualitySource}.
              </>
            ) : (
              <>
                <strong>Inadequada</strong> para avaliação, segundo a {qualitySource}. Os achados abaixo devem ser
                interpretados com cautela, e a repetição do exame deve ser considerada.
              </>
            )}
          </p>
        </Section>

        <Section title="Achados">
          {data.findings.length === 0 ? (
            <p>Nenhum achado confirmado pelo profissional neste exame.</p>
          ) : (
            <>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-600" style={PRINT_COLORS}>
                    <th className="border border-slate-300 px-3 py-1.5 font-semibold">Achado</th>
                    <th className="w-28 border border-slate-300 px-3 py-1.5 text-center font-semibold">Quantidade</th>
                    <th className="w-48 border border-slate-300 px-3 py-1.5 font-semibold">Número na imagem</th>
                  </tr>
                </thead>
                <tbody>
                  {data.groups.map((group) => (
                    <tr key={group.class_code}>
                      <td className="border border-slate-300 px-3 py-1.5">
                        {group.label}
                        {data.findings.some((f) => f.class_code === group.class_code && f.low_reliability) && " *"}
                      </td>
                      <td className="border border-slate-300 px-3 py-1.5 text-center">{group.count}</td>
                      <td className="border border-slate-300 px-3 py-1.5">{group.numbers.join(", ")}</td>
                    </tr>
                  ))}
                  <tr className="font-semibold">
                    <td className="border border-slate-300 px-3 py-1.5">Total</td>
                    <td className="border border-slate-300 px-3 py-1.5 text-center">{data.findings.length}</td>
                    <td className="border border-slate-300 px-3 py-1.5" />
                  </tr>
                </tbody>
              </table>

              <p className="mt-2 text-xs text-slate-500">
                Achados sugeridos por inteligência artificial e confirmados por {validators || "profissional da clínica"}.
                {data.discarded_count > 0 &&
                  ` ${data.discarded_count} ${data.discarded_count === 1 ? "sugestão foi descartada" : "sugestões foram descartadas"} na conferência.`}
                {hasFlagged && " * Tipo de achado em que a detecção automática é menos confiável."}
              </p>
            </>
          )}
        </Section>

        <Section title="Imagem">
          {imageUrl ? (
            <div className="relative inline-block w-full">
              <img src={imageUrl} alt="Radiografia do exame" className="block w-full" />
              {data.findings.map((finding) => (
                <div
                  key={finding.number}
                  className="absolute"
                  style={{
                    left: `${finding.bbox.x * 100}%`,
                    top: `${finding.bbox.y * 100}%`,
                    width: `${finding.bbox.width * 100}%`,
                    height: `${finding.bbox.height * 100}%`,
                    border: `1.5px solid ${MARKER}`
                  }}
                >
                  <span
                    className="absolute -top-[15px] left-[-1.5px] px-1 text-[10px] font-bold leading-[14px] text-slate-900"
                    style={{ backgroundColor: MARKER, ...PRINT_COLORS }}
                  >
                    {finding.number}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500">A imagem deste exame não está mais disponível.</p>
          )}
          {imageUrl && data.findings.length > 0 && (
            <p className="mt-1 text-xs text-slate-500">
              Os números correspondem à coluna "Número na imagem" da tabela de achados.
            </p>
          )}
        </Section>

        <Section title="Observações">
          {report.notes ? <p className="whitespace-pre-wrap">{report.notes}</p> : <p className="text-slate-500">Sem observações.</p>}
        </Section>

        {/* Assinatura */}
        <div className="mt-14 break-inside-avoid">
          <div className="mx-auto w-72 border-t border-slate-500 pt-1.5 text-center text-xs text-slate-600">
            Cirurgião-dentista responsável
            <br />
            Nome e CRO
          </div>
        </div>

        {/* Ressalvas */}
        <footer className="mt-10 break-inside-avoid border-t border-slate-300 pt-3 text-[10.5px] leading-snug text-slate-500">
          <p>
            <strong>Este documento é um pré-laudo de apoio ao diagnóstico e não substitui o laudo nem a avaliação do
            cirurgião-dentista.</strong>{" "}
            A detecção automática pode deixar de identificar achados: a ausência de um item neste documento não
            significa que ele não exista.
          </p>
          <p className="mt-1 text-slate-400">
            Arquivo {data.exam.file_name} · Análise: {quality.model_version ?? "—"} e {data.detector_model ?? "—"} ·
            Documento {report.id}
          </p>
        </footer>
      </article>
    </div>
  );
}

function InfoCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <td className="w-1/2 border border-slate-300 px-3 py-1.5 align-top">
      <span className="block text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{children}</span>
    </td>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6 break-inside-avoid">
      <h2 className="mb-2 border-b border-slate-300 pb-1 text-[11px] font-semibold uppercase tracking-widest text-slate-700">
        {title}
      </h2>
      {children}
    </section>
  );
}
