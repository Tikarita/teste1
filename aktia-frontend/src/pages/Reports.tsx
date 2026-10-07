import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import type { ReportSummary } from "../lib/types";

/** Primeiro e último dia de um mês "AAAA-MM", limitando o fim a hoje. */
function monthBounds(month: string) {
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(year, monthNumber, 0).getDate();
  const today = toIsoDate(new Date());
  const end = `${month}-${String(lastDay).padStart(2, "0")}`;

  return { start: `${month}-01`, end: end > today ? today : end };
}

function toIsoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleDateString("pt-BR") : "—";
}

/** O período é guardado como [início, fim): o último dia é a véspera do fim. */
export function formatPeriod(start: string | null | undefined, end: string | null | undefined) {
  if (!start || !end) return "—";
  const lastDay = new Date(new Date(end).getTime() - 1);
  return `${formatDate(start)} a ${lastDay.toLocaleDateString("pt-BR")}`;
}

export default function Reports() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canIssue = user?.role === "admin" || user?.role === "manager";

  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [month, setMonth] = useState(toIsoDate(new Date()).slice(0, 7));
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listQualityReports()
      .then(setReports)
      .catch((err) => setListError(err instanceof Error ? err.message : "Erro ao carregar relatórios"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!month) return;

    setSubmitting(true);
    setFormError(null);

    try {
      const { start, end } = monthBounds(month);
      const report = await api.createQualityReport({ period_start: start, period_end: end, notes });
      navigate(`/relatorios/${report.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Erro ao emitir relatório");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Relatórios de Garantia da Qualidade</h1>
        <p className="text-sm text-slate-500">
          Registro da avaliação de qualidade das radiografias por período, para o Programa de Garantia da
          Qualidade exigido pela RDC ANVISA nº 611/2022.
        </p>
      </div>

      {canIssue ? (
        <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-1 text-sm font-semibold text-slate-700">Emitir relatório</h2>
          <p className="mb-3 text-xs text-slate-500">
            O relatório é gravado com os números do momento da emissão e não pode ser alterado depois. Para
            um mês em andamento, ele cobre até hoje.
          </p>

          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Mês de referência</label>
              <input
                required
                type="month"
                value={month}
                max={toIsoDate(new Date()).slice(0, 7)}
                onChange={(e) => setMonth(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Ações corretivas e observações (opcional)
              </label>
              <textarea
                value={notes}
                maxLength={5000}
                rows={3}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ex.: reorientação da equipe sobre posicionamento; manutenção do equipamento em 12/10."
              />
            </div>
          </div>

          {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}

          <button
            type="submit"
            disabled={submitting || !month}
            className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {submitting ? "Emitindo..." : "Emitir relatório"}
          </button>
        </form>
      ) : (
        <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
          Apenas administradores e gestores da clínica podem emitir relatórios. Você pode consultar os já
          emitidos abaixo.
        </p>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Relatórios emitidos ({reports.length})</h2>

        {loading && <p className="text-sm text-slate-400">Carregando...</p>}
        {listError && <p className="text-sm text-red-600">{listError}</p>}

        {!loading && !listError && reports.length === 0 && (
          <p className="text-sm text-slate-400">Nenhum relatório emitido ainda.</p>
        )}

        {reports.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                <th className="pb-2">Período</th>
                <th className="pb-2">Emitido em</th>
                <th className="pb-2">Emitido por</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reports.map((report) => (
                <tr key={report.id}>
                  <td className="py-2 font-medium">{formatPeriod(report.period_start, report.period_end)}</td>
                  <td className="py-2 text-slate-500">{new Date(report.created_at).toLocaleString("pt-BR")}</td>
                  <td className="py-2 text-slate-500">{report.generated_by_name ?? "—"}</td>
                  <td className="py-2 text-right">
                    <Link to={`/relatorios/${report.id}`} className="font-medium text-slate-700 hover:underline">
                      Abrir
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
