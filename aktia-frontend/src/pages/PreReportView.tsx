import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { colorFor } from "../lib/findingColors";
import type { PreReport } from "../lib/types";

// Garante que as cores de fundo saiam na impressão e no PDF.
const PRINT_COLORS: CSSProperties = { printColorAdjust: "exact", WebkitPrintColorAdjust: "exact" };

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
  const qualitySource = quality.review_verdict !== null ? "revisão do profissional" : "classificação automática";

  return (
    <div className="mx-auto max-w-4xl space-y-4">
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

      <article className="overflow-hidden rounded-xl border border-slate-200 bg-white print:rounded-none print:border-0">
        {/* Faixa de título */}
        <header className="bg-slate-900 px-8 py-6 text-white" style={PRINT_COLORS}>
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-300">AktIA · {data.clinic.name}</p>
              <h1 className="mt-1 text-2xl font-semibold">Pré-laudo radiográfico</h1>
              <p className="mt-1 text-sm text-slate-300">Documento de apoio ao diagnóstico. Não é um laudo.</p>
            </div>
            <div className="shrink-0 rounded-lg bg-white/10 px-4 py-2 text-right" style={PRINT_COLORS}>
              <p className="text-[11px] uppercase tracking-wide text-slate-300">Código do paciente</p>
              <p className="text-lg font-semibold">{data.exam.patient_code ?? "não informado"}</p>
            </div>
          </div>
        </header>

        <div className="space-y-8 px-8 py-6">
          {/* Dados do exame */}
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm md:grid-cols-4">
            <Field label="Data do exame">{new Date(data.exam.uploaded_at).toLocaleDateString("pt-BR")}</Field>
            <Field label="Realizado por">{data.exam.professional_name ?? "não informado"}</Field>
            <Field label="Pré-laudo emitido por">{data.issued_by.full_name ?? "—"}</Field>
            <Field label="Emitido em">{new Date(report.created_at).toLocaleString("pt-BR")}</Field>
          </dl>

          {/* Resumo: o que o leitor precisa saber em 5 segundos */}
          <section className="grid gap-4 md:grid-cols-3">
            <div
              className={`rounded-lg border-2 p-4 ${
                adequate === null
                  ? "border-slate-200 bg-slate-50"
                  : adequate
                  ? "border-emerald-300 bg-emerald-50"
                  : "border-red-300 bg-red-50"
              }`}
              style={PRINT_COLORS}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Qualidade da imagem</p>
              <p
                className={`mt-1 text-xl font-semibold ${
                  adequate === null ? "text-slate-700" : adequate ? "text-emerald-800" : "text-red-800"
                }`}
              >
                {adequate === null ? "Não avaliada" : adequate ? "Adequada" : "Inadequada"}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Segundo a {qualitySource}
                {quality.review_by && ` (${quality.review_by})`}.
              </p>
            </div>

            <div className="rounded-lg border-2 border-slate-200 bg-slate-50 p-4 md:col-span-2" style={PRINT_COLORS}>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Resumo dos achados</p>
              {data.findings.length === 0 ? (
                <p className="mt-1 text-xl font-semibold text-slate-700">Nenhum achado confirmado</p>
              ) : (
                <>
                  <p className="mt-1 text-xl font-semibold text-slate-900">
                    {data.findings.length} {data.findings.length === 1 ? "achado confirmado" : "achados confirmados"}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {data.groups.map((group) => (
                      <span
                        key={group.class_code}
                        className="rounded-full px-3 py-1 text-sm font-medium text-white"
                        style={{ backgroundColor: colorFor(group.class_code), ...PRINT_COLORS }}
                      >
                        {group.count} × {group.label}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </section>

          {adequate === false && (
            <p
              className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-900"
              style={PRINT_COLORS}
            >
              Atenção: a imagem foi considerada inadequada para diagnóstico. Os achados deste documento devem ser
              lidos com cautela, e a repetição do exame deve ser avaliada.
            </p>
          )}

          {/* Imagem */}
          <section className="break-inside-avoid">
            <SectionTitle number={1}>Onde estão os achados</SectionTitle>
            <p className="mb-3 text-sm text-slate-500">
              Cada número na imagem corresponde a uma linha da lista abaixo. A cor indica o tipo de achado.
            </p>
            {imageUrl ? (
              <div className="relative inline-block w-full">
                <img src={imageUrl} alt="Radiografia do exame" className="w-full rounded-lg" />
                {data.findings.map((finding) => (
                  <div
                    key={finding.number}
                    className="absolute rounded-sm border-2"
                    style={{
                      left: `${finding.bbox.x * 100}%`,
                      top: `${finding.bbox.y * 100}%`,
                      width: `${finding.bbox.width * 100}%`,
                      height: `${finding.bbox.height * 100}%`,
                      borderColor: colorFor(finding.class_code)
                    }}
                  >
                    <span
                      className="absolute -left-0.5 -top-5 min-w-5 rounded px-1 text-center text-xs font-bold text-white"
                      style={{ backgroundColor: colorFor(finding.class_code), ...PRINT_COLORS }}
                    >
                      {finding.number}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                A imagem deste exame não está mais disponível.
              </p>
            )}
          </section>

          {/* Lista de achados, agrupada por tipo */}
          <section>
            <SectionTitle number={2}>Lista de achados</SectionTitle>

            {data.findings.length === 0 ? (
              <p className="text-sm text-slate-600">
                O profissional não confirmou nenhum achado neste exame.
              </p>
            ) : (
              <div className="space-y-3">
                {data.groups.map((group) => (
                  <div
                    key={group.class_code}
                    className="break-inside-avoid overflow-hidden rounded-lg border border-slate-200"
                  >
                    <div
                      className="flex items-center justify-between px-4 py-2 text-white"
                      style={{ backgroundColor: colorFor(group.class_code), ...PRINT_COLORS }}
                    >
                      <p className="font-semibold">
                        {group.label} <span className="text-xs font-normal opacity-80">({group.class_code})</span>
                      </p>
                      <p className="text-sm font-medium">
                        {group.count} {group.count === 1 ? "achado" : "achados"}
                      </p>
                    </div>

                    <ul className="divide-y divide-slate-100">
                      {data.findings
                        .filter((finding) => finding.class_code === group.class_code)
                        .map((finding) => (
                          <li key={finding.number} className="flex items-center justify-between gap-4 px-4 py-2 text-sm">
                            <span className="flex items-center gap-3">
                              <span
                                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                                style={{ backgroundColor: colorFor(finding.class_code), ...PRINT_COLORS }}
                              >
                                {finding.number}
                              </span>
                              <span className="text-slate-800">{finding.label}</span>
                              {finding.low_reliability && (
                                <span
                                  className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800"
                                  style={PRINT_COLORS}
                                >
                                  conferir com atenção
                                </span>
                              )}
                            </span>
                            <span className="shrink-0 text-right text-xs text-slate-500">
                              Confirmado por {finding.validated_by_name ?? "—"}
                              <span className="ml-2 text-slate-400">
                                (IA: {Math.round(finding.confidence * 100)}% de confiança)
                              </span>
                            </span>
                          </li>
                        ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}

            <p className="mt-3 text-xs text-slate-500">
              A inteligência artificial sugeriu {data.detected_count}{" "}
              {data.detected_count === 1 ? "achado" : "achados"}; o profissional confirmou {data.findings.length} e
              descartou {data.discarded_count}.
              {data.findings.some((finding) => finding.low_reliability) &&
                ' "Conferir com atenção" marca os tipos de achado em que a IA costuma errar mais.'}
            </p>
          </section>

          {/* Observações */}
          <section className="break-inside-avoid">
            <SectionTitle number={3}>Observações do profissional</SectionTitle>
            {report.notes ? (
              <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800" style={PRINT_COLORS}>
                {report.notes}
              </p>
            ) : (
              <p className="text-sm text-slate-500">Nenhuma observação registrada.</p>
            )}
          </section>

          {/* Como ler */}
          <section className="break-inside-avoid rounded-lg border border-slate-200 bg-slate-50 p-4" style={PRINT_COLORS}>
            <p className="text-sm font-semibold text-slate-800">Como ler este documento</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
              <li>Este é um pré-laudo: ajuda na leitura do exame, mas não substitui a avaliação do cirurgião-dentista.</li>
              <li>Os achados foram sugeridos por inteligência artificial e só constam aqui os que o profissional confirmou.</li>
              <li>
                A IA pode deixar de detectar achados. Se algo não aparece neste documento, isso não significa que não
                exista.
              </li>
            </ul>
          </section>

          {/* Assinatura */}
          <footer className="break-inside-avoid pt-8">
            <div className="mx-auto w-2/3 border-t border-slate-400 pt-2 text-center text-sm text-slate-600">
              Cirurgião-dentista responsável (nome e CRO)
            </div>

            <div className="mt-8 space-y-1 border-t border-slate-100 pt-3 text-[10px] leading-relaxed text-slate-400">
              {data.disclaimer.map((line, i) => (
                <p key={i}>{line}</p>
              ))}
              <p>
                Arquivo: {data.exam.file_name} · Modelos: qualidade {quality.model_version ?? "não informado"}, detecção{" "}
                {data.detector_model ?? "não informado"} · {data.clinic.cnpj ? `CNPJ ${data.clinic.cnpj} · ` : ""}
                Documento {report.id}
              </p>
            </div>
          </footer>
        </div>
      </article>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 font-medium text-slate-800">{children}</dd>
    </div>
  );
}

function SectionTitle({ number, children }: { number: number; children: ReactNode }) {
  return (
    <h2 className="mb-2 flex items-center gap-2 text-base font-semibold text-slate-900">
      <span
        className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white"
        style={PRINT_COLORS}
      >
        {number}
      </span>
      {children}
    </h2>
  );
}
