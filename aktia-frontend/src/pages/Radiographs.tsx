import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useClinics } from "../context/ClinicContext";
import type { Radiograph, StaffMember } from "../lib/types";

export default function Radiographs() {
  const { clinics, selectedClinicId } = useClinics();
  const [radiographs, setRadiographs] = useState<Radiograph[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [uploadedBy, setUploadedBy] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
        setUploadedBy((current) => current || res.data[0]?.id || "");
      })
      .catch(() => setStaff([]));
  }, [selectedClinicId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedClinicId || !file || !uploadedBy) return;

    setSubmitting(true);
    setFormError(null);

    try {
      await api.uploadRadiograph({ clinic_id: selectedClinicId, uploaded_by: uploadedBy, file });
      setFile(null);
      loadRadiographs();
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

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Enviado por</label>
            <select
              value={uploadedBy}
              onChange={(e) => setUploadedBy(e.target.value)}
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
          disabled={submitting || !file || !uploadedBy}
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
