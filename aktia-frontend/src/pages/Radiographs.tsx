import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useClinics } from "../context/ClinicContext";
import { REFRESH_NOTIFICATIONS_EVENT } from "../components/NotificationCenter";
import { useToasts } from "../context/ToastContext";
import type { Radiograph, StaffMember } from "../lib/types";

// VITE_ENABLE_AI=false desliga a análise automática logo após o envio.
const AI_ENABLED = import.meta.env.VITE_ENABLE_AI !== "false";

export default function Radiographs() {
  const { clinics, selectedClinicId } = useClinics();
  const { user } = useAuth();
  const [radiographs, setRadiographs] = useState<Radiograph[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [professionalId, setProfessionalId] = useState("");
  const [patientCode, setPatientCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { showToast, dismissToast } = useToasts();

  function loadRadiographs() {
    if (!selectedClinicId) {
      setRadiographs([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setListError(null);

    api
      .listRadiographsByClinic(selectedClinicId)
      .then((res) => setRadiographs(res.data))
      .catch((err) => setListError(err instanceof Error ? err.message : "Erro ao carregar radiografias"))
      .finally(() => setLoading(false));
  }

  useEffect(loadRadiographs, [selectedClinicId]);

  useEffect(() => {
    if (!selectedClinicId) {
      setStaff([]);
      return;
    }

    api
      .listStaffByClinic(selectedClinicId)
      .then((res) => {
        setStaff(res.data);
        setProfessionalId(
          (current) => current || res.data.find((member) => member.id === user?.id)?.id || res.data[0]?.id || ""
        );
      })
      .catch(() => setStaff([]));
  }, [selectedClinicId, user?.id]);

  // Analisa a radiografia recém-enviada e avisa o resultado no canto da tela,
  // enquanto o paciente ainda está na clínica.
  async function analyzeUploaded(radiograph: Radiograph) {
    const key = `upload-${radiograph.id}`;
    showToast({
      key,
      tone: "info",
      title: "Analisando a radiografia...",
      message: `${radiograph.file_name} · leva alguns segundos.`
    });

    try {
      const analysis = await api.analyzeRadiograph(radiograph.id);
      loadRadiographs();

      if (analysis.data.efficientnet.is_adequate) {
        showToast({
          key,
          tone: "success",
          title: "Imagem adequada",
          message: `${radiograph.file_name} · a IA liberou o pré-laudo.`,
          link: { to: `/radiografias/${radiograph.id}`, label: "Ver pré-laudo" },
          autoCloseMs: 12_000
        });
      } else {
        // O alerta de exame inadequado vem do backend como aviso (o mesmo que
        // chega ao profissional responsável): só pede a checagem imediata.
        dismissToast(key);
        window.dispatchEvent(new Event(REFRESH_NOTIFICATIONS_EVENT));
      }
    } catch (err) {
      showToast({
        key,
        tone: "danger",
        title: "A radiografia foi enviada, mas não pôde ser analisada",
        message: err instanceof ApiError ? err.message : "Erro inesperado.",
        link: { to: `/radiografias/${radiograph.id}`, label: "Abrir exame" }
      });
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedClinicId || !file || !professionalId) return;

    setSubmitting(true);
    setFormError(null);

    try {
      const uploaded = await api.uploadRadiograph({
        professional_id: professionalId,
        patient_code: patientCode,
        file
      });
      setFile(null);
      setPatientCode("");
      loadRadiographs();

      if (AI_ENABLED && uploaded.data[0]) {
        // Não espera a análise para liberar o formulário: o retorno aparece
        // no cartão acima assim que ficar pronto.
        void analyzeUploaded(uploaded.data[0]);
      }
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Erro ao enviar radiografia");
    } finally {
      setSubmitting(false);
    }
  }

  if (clinics.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Cadastre uma clínica primeiro para poder enviar radiografias.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Radiografias</h1>
        <p className="text-sm text-slate-500">Envie e acompanhe as radiografias da clínica selecionada.</p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Enviar radiografia</h2>

        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Código do paciente (opcional)</label>
            <input
              value={patientCode}
              maxLength={60}
              onChange={(e) => setPatientCode(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Nº do prontuário"
            />
            <p className="mt-1 text-[11px] text-slate-400">Use só o código da clínica. Não digite nome nem CPF.</p>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Profissional responsável pela captura</label>
            <select
              value={professionalId}
              onChange={(e) => setProfessionalId(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              disabled={staff.length === 0}
            >
              {staff.length === 0 && <option value="">Nenhum funcionário nesta clínica</option>}
              {staff.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Arquivo (JPG ou PNG)</label>
            <input
              required
              type="file"
              accept="image/jpeg,image/png,image/jpg"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
        </div>

        {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}

        <button
          type="submit"
          disabled={submitting || !file || !professionalId}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? "Enviando..." : "Enviar radiografia"}
        </button>
      </form>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Radiografias enviadas</h2>

        {loading && <p className="text-sm text-slate-400">Carregando...</p>}
        {listError && <p className="text-sm text-red-600">{listError}</p>}

        {!loading && !listError && radiographs.length === 0 && (
          <p className="text-sm text-slate-400">Nenhuma radiografia enviada nesta clínica.</p>
        )}

        {!loading && radiographs.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                <th className="pb-2">Arquivo</th>
                <th className="pb-2">Tipo</th>
                <th className="pb-2">Tamanho</th>
                <th className="pb-2">Análise</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {radiographs.map((rad) => (
                <tr key={rad.id}>
                  <td className="py-2">{rad.file_name}</td>
                  <td className="py-2 text-slate-500">{rad.file_type}</td>
                  <td className="py-2 text-slate-500">{(rad.file_size / 1024).toFixed(0)} KB</td>
                  <td className="py-2">
                    {rad.analysis_result ? (
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                          rad.analysis_result.efficientnet.is_adequate
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : "border-amber-200 bg-amber-50 text-amber-700"
                        }`}
                      >
                        {rad.analysis_result.efficientnet.is_adequate ? "Adequado" : "Atenção"}
                      </span>
                    ) : (
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
                        Pendente
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <Link to={`/radiografias/${rad.id}`} className="text-sm font-medium text-slate-700 hover:underline">
                      Ver detalhes
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
