import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { REVIEW_REASONS } from "../components/ReviewCard";
import type { PreReport, ReportFormat } from "../lib/types";

// Garante que os fundos (marcadores na imagem, cabeçalho da tabela) saiam na impressão.
const PRINT_COLORS: CSSProperties = { printColorAdjust: "exact", WebkitPrintColorAdjust: "exact" };

// Uma cor só para todas as marcações: o documento é lido pelos números.
const MARKER = "#facc15";

const REASON_LABELS = Object.fromEntries(REVIEW_REASONS.map((reason) => [reason.value, reason.label.toLowerCase()]));

const FORMATS: Record<ReportFormat, { label: string; reference: string }> = {
  esr: {
    label: "ESR",
    reference:
      "Estrutura conforme European Society of Radiology — Good practice for radiological reporting (2011)."
  },
  acr: {
    label: "ACR",
    reference:
      "Estrutura conforme American College of Radiology — Practice Parameter for Communication of Diagnostic Imaging Findings."
  }
};

/**
 * Pré-laudo no formato de laudo radiológico, em duas estruturas:
 *
 *  - ESR: indicação clínica, técnica, achados (com a comparação), impressão /
 *    conclusão, recomendações e validação.
 *  - ACR: dados demográficos, informações clínicas, corpo do relatório
 *    (procedimento, achados, limitações, questões clínicas, comparação) e
 *    impressão, que inclui o seguimento sugerido.
 *
 * O conteúdo é o mesmo nos dois; mudam a ordem e os títulos. Mostra exatamente
 * o que foi gravado na emissão (report.data). A imagem vem do exame: se a
 * radiografia for excluída, o documento continua com os achados, sem a figura.
 */
export default function PreReportView() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
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
  const referral = data.referral ?? { exam_type: "Radiografia panorâmica", requested_by: null, clinical_indication: null };
  const technical = data.exam_metadata ?? null;

  // O formato escolhido na emissão vale por padrão; ?formato= mostra o outro.
  const requested = searchParams.get("formato");
  const format: ReportFormat = requested === "esr" || requested === "acr" ? requested : data.report_format ?? "esr";

  // A revisão do profissional, quando existe, é a que vale para o documento.
  const adequate = quality.review_verdict !== null ? quality.review_verdict === "adequate" : quality.ai_is_adequate;
  const qualitySource =
    quality.review_verdict !== null
      ? `avaliação do profissional${quality.review_by ? ` (${quality.review_by})` : ""}`
      : "classificação automática";
  const defects = (quality.review_reasons ?? []).map((reason) => REASON_LABELS[reason] ?? reason);

  const equipment = [technical?.manufacturer, technical?.model].filter(Boolean).join(" ");
  const parameters = [
    technical?.kvp !== undefined && `${technical.kvp} kV`,
    technical?.tube_current_ma !== undefined && `${technical.tube_current_ma} mA`,
    technical?.exposure_time_ms !== undefined && `${technical.exposure_time_ms} ms`
  ]
    .filter(Boolean)
    .join(", ");

  const validators = [...new Set(data.findings.map((f) => f.validated_by_name).filter(Boolean))].join(", ");
  const hasFlagged = data.findings.some((f) => f.low_reliability);

  // --- Blocos de conteúdo, iguais nos dois formatos --------------------------

  const procedure = (
    <p>
      {referral.exam_type}
      {equipment && `, obtida em equipamento ${equipment}`}
      {parameters && ` (${parameters})`}.
    </p>
  );

  const technicalQuality = (
    <p>
      Qualidade técnica:{" "}
      {adequate === null ? (
        "não avaliada."
      ) : adequate ? (
        <>
          <strong>adequada</strong> para avaliação, segundo a {qualitySource}.
        </>
      ) : (
        <>
          <strong>inadequada</strong> para avaliação, segundo a {qualitySource}
          {defects.length > 0 && ` (${defects.join(", ")})`}. Os achados devem ser interpretados com cautela, e a
          repetição do exame deve ser considerada.
        </>
      )}
    </p>
  );

  const limitations = (
    <p>
      Os achados foram sugeridos por detecção automática e conferidos pelo profissional. A detecção automática não
      avalia todas as estruturas e pode deixar de identificar alterações.
    </p>
  );

  const findings = (
    <>
      {data.findings.length === 0 ? (
        <p>Nenhum achado confirmado pelo profissional entre os sugeridos pela detecção automática.</p>
      ) : (
        <>
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-600" style={PRINT_COLORS}>
                <th className="border border-slate-300 px-3 py-1.5 font-semibold">Achado</th>
                <th className="w-28 border border-slate-300 px-3 py-1.5 text-center font-semibold">Quantidade</th>
                <th className="w-48 border border-slate-300 px-3 py-1.5 font-semibold">Localização (Figura 1)</th>
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
                  <td className="border border-slate-300 px-3 py-1.5">
                    {group.numbers.length === 1 ? "Marcação" : "Marcações"} {group.numbers.join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="mt-2 text-xs text-slate-500">
            Achados conferidos por {validators || "profissional da clínica"}.
            {data.discarded_count > 0 &&
              ` ${data.discarded_count} ${data.discarded_count === 1 ? "sugestão da detecção automática foi descartada" : "sugestões da detecção automática foram descartadas"} na conferência.`}
            {hasFlagged && " * Tipo de achado em que a detecção automática é menos confiável."}
          </p>
        </>
      )}

      {imageUrl ? (
        <figure className="mt-4 break-inside-avoid">
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
          <figcaption className="mt-1 text-xs text-slate-500">
            Figura 1 — {referral.exam_type}
            {data.findings.length > 0 && " com as marcações numeradas dos achados"}.
          </figcaption>
        </figure>
      ) : (
        <p className="mt-3 text-slate-500">A imagem deste exame não está mais disponível.</p>
      )}
    </>
  );

  const comparison = <p>Não realizada: não há exames anteriores disponíveis para comparação.</p>;

  const impression = data.impression ? (
    <p className="whitespace-pre-wrap">{data.impression}</p>
  ) : (
    <>
      <p className="text-xs text-slate-500">A ser preenchida pelo cirurgião-dentista responsável.</p>
      <div className="mt-1 space-y-6 pt-5">
        <div className="border-b border-slate-300" />
        <div className="border-b border-slate-300" />
        <div className="border-b border-slate-300" />
      </div>
    </>
  );

  const clinicalInformation = <p className="whitespace-pre-wrap">{referral.clinical_indication ?? "Não informada."}</p>;

  return (
    <div className="mx-auto max-w-[210mm] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link
          to={report.radiograph_id ? `/radiografias/${report.radiograph_id}` : "/radiografias"}
          className="text-sm text-slate-500 hover:underline"
        >
          &larr; Voltar ao exame
        </Link>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            Formato
            <div className="flex rounded-md border border-slate-200 bg-white p-0.5">
              {(Object.keys(FORMATS) as ReportFormat[]).map((option) => (
                <button
                  key={option}
                  onClick={() => setSearchParams({ formato: option }, { replace: true })}
                  className={`rounded px-3 py-1 text-sm ${
                    format === option ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {FORMATS[option].label}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => window.print()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            Imprimir / salvar em PDF
          </button>
        </div>
      </div>

      <article className="bg-white px-12 py-10 text-[13px] leading-relaxed text-slate-800 shadow-sm ring-1 ring-slate-200 print:p-0 print:shadow-none print:ring-0">
        {/* Serviço emissor e tipo de documento */}
        <header className="flex items-end justify-between gap-6 border-b-2 border-slate-800 pb-3">
          <div>
            <p className="text-lg font-semibold text-slate-900">{data.clinic.name}</p>
            {data.clinic.cnpj && <p className="text-xs text-slate-500">CNPJ {data.clinic.cnpj}</p>}
          </div>
          <div className="text-right">
            <p className="text-lg font-semibold tracking-wide text-slate-900">PRÉ-LAUDO RADIOGRÁFICO</p>
            <p className="text-xs text-slate-500">Relatório preliminar · Nº {report.id.slice(0, 8).toUpperCase()}</p>
          </div>
        </header>

        {format === "acr" && <SectionTitle>1. Dados demográficos</SectionTitle>}

        <table className={`${format === "acr" ? "" : "mt-4"} w-full border-collapse`}>
          <tbody>
            {format === "acr" && (
              <tr>
                <InfoCell label="Serviço onde o exame foi realizado" span>
                  {data.clinic.name}
                </InfoCell>
              </tr>
            )}
            <tr>
              <InfoCell label="Paciente (código do prontuário)">{data.exam.patient_code ?? "Não informado"}</InfoCell>
              <InfoCell label={format === "acr" ? "Nome ou tipo do exame" : "Exame"}>{referral.exam_type}</InfoCell>
            </tr>
            <tr>
              <InfoCell label="Data do exame">{new Date(data.exam.uploaded_at).toLocaleDateString("pt-BR")}</InfoCell>
              <InfoCell label="Profissional solicitante">{referral.requested_by ?? "Não informado"}</InfoCell>
            </tr>
            <tr>
              <InfoCell label="Exame realizado por">{data.exam.professional_name ?? "Não informado"}</InfoCell>
              <InfoCell label={format === "acr" ? "Data e hora de finalização do relatório" : "Data de emissão"}>
                {new Date(report.created_at).toLocaleString("pt-BR")}
              </InfoCell>
            </tr>
          </tbody>
        </table>

        {format === "esr" ? (
          <>
            <Section title="Indicação clínica">{clinicalInformation}</Section>

            <Section title="Técnica">
              {procedure}
              {technicalQuality}
              <p>Limitações:</p>
              {limitations}
            </Section>

            <Section title="Achados">
              {findings}
              <p className="pt-2">Comparação com exames anteriores:</p>
              {comparison}
            </Section>

            <Section title="Impressão / conclusão">{impression}</Section>

            <Section title="Recomendações">
              {report.notes ? <p className="whitespace-pre-wrap">{report.notes}</p> : <p>Sem recomendações registradas.</p>}
            </Section>
          </>
        ) : (
          <>
            <Section title="2. Informações clínicas relevantes">{clinicalInformation}</Section>

            <SectionTitle>3. Corpo do relatório</SectionTitle>
            <SubSection title="a) Procedimento e materiais">
              {procedure}
              <p>Sem uso de meio de contraste ou medicação.</p>
            </SubSection>
            <SubSection title="b) Achados">{findings}</SubSection>
            <SubSection title="c) Limitações potenciais">
              {technicalQuality}
              {limitations}
            </SubSection>
            <SubSection title="d) Questões clínicas">
              <p>
                {referral.clinical_indication
                  ? "A resposta à indicação clínica informada consta na impressão."
                  : "Nenhuma pergunta clínica específica foi informada."}
              </p>
            </SubSection>
            <SubSection title="e) Comparação com exames e relatórios anteriores">{comparison}</SubSection>

            <Section title="4. Impressão (conclusão ou diagnóstico)">
              {impression}
              {report.notes && (
                <>
                  <p className="pt-2">Seguimento e exames complementares sugeridos:</p>
                  <p className="whitespace-pre-wrap">{report.notes}</p>
                </>
              )}
            </Section>
          </>
        )}

        {/* Validação */}
        <div className="mt-14 break-inside-avoid">
          <div className="mx-auto w-80 border-t border-slate-500 pt-1.5 text-center text-xs text-slate-600">
            Cirurgião-dentista responsável
            <br />
            Nome, CRO e assinatura
          </div>
        </div>

        <footer className="mt-10 break-inside-avoid border-t border-slate-300 pt-3 text-[10.5px] leading-snug text-slate-500">
          <p>
            <strong>
              Documento preliminar de apoio ao diagnóstico. Só tem valor de laudo depois de revisado, concluído e
              assinado pelo cirurgião-dentista responsável.
            </strong>
          </p>
          <p className="mt-1 text-slate-400">
            {FORMATS[format].reference} Emitido por {data.issued_by.full_name ?? "—"} · Arquivo {data.exam.file_name} ·
            Análise automática: {quality.model_version ?? "—"} e {data.detector_model ?? "—"} · Documento {report.id}
          </p>
        </footer>
      </article>
    </div>
  );
}

function InfoCell({ label, children, span = false }: { label: string; children: ReactNode; span?: boolean }) {
  return (
    <td colSpan={span ? 2 : 1} className="w-1/2 border border-slate-300 px-3 py-1.5 align-top">
      <span className="block text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{children}</span>
    </td>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-1.5 mt-5 border-b border-slate-300 pb-1 text-[11px] font-semibold uppercase tracking-widest text-slate-700">
      {children}
    </h2>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function SubSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-3">
      <h3 className="mb-1 text-[12px] font-semibold text-slate-800">{title}</h3>
      <div className="space-y-1">{children}</div>
    </section>
  );
}
