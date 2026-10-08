import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useClinics } from "../context/ClinicContext";
import type { Radiograph, StaffMember } from "../lib/types";

// VITE_ENABLE_AI=false abre o exame sem disparar a análise.
const AI_ENABLED = import.meta.env.VITE_ENABLE_AI !== "false";

const ACCEPTED_FILES = "image/jpeg,image/png,image/jpg,.dcm,.dicom,application/dicom";

export default function Radiographs() {
  const { clinics, selectedClinicId } = useClinics();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [radiographs, setRadiographs] = useState<Radiograph[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [professionalId, setProfessionalId] = useState("");
  const [patientCode, setPatientCode] = useState("");
  const [uploading, setUploading] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

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

  // Escolher (ou soltar) o arquivo já envia: não há botão de enviar. Assim que
  // o envio termina, a tela do exame abre e a classificação começa sozinha.
  async function sendFile(file: File | undefined) {
    if (!file || !selectedClinicId || !professionalId || uploading) return;

    setUploading(file.name);
    setFormError(null);

    try {
      const uploaded = await api.uploadRadiograph({
        professional_id: professionalId,
        patient_code: patientCode,
        file
      });
      navigate(`/radiografias/${uploaded.data[0].id}${AI_ENABLED ? "?analisar=1" : ""}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Erro ao enviar radiografia");
      setUploading(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    void sendFile(e.dataTransfer.files?.[0]);
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

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Novo exame</h2>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Código do paciente (opcional)</label>
            <input
              value={patientCode}
              maxLength={60}
              disabled={uploading !== null}
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
              disabled={staff.length === 0 || uploading !== null}
            >
              {staff.length === 0 && <option value="">Nenhum funcionário nesta clínica</option>}
              {staff.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
            dragging ? "border-slate-900 bg-slate-100" : "border-slate-300 bg-slate-50 hover:border-slate-400"
          } ${uploading || !professionalId ? "pointer-events-none opacity-60" : ""}`}
        >
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPTED_FILES}
            className="hidden"
            disabled={uploading !== null || !professionalId}
            onChange={(e) => void sendFile(e.target.files?.[0])}
          />
          {uploading ? (
            <>
              <p className="text-sm font-medium text-slate-800">Enviando {uploading}...</p>
              <p className="mt-1 text-xs text-slate-500">A tela do exame abre em seguida, já com a classificação.</p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-800">Clique para escolher a radiografia ou arraste o arquivo para cá</p>
              <p className="mt-1 text-xs text-slate-500">
                JPG, PNG ou DICOM. O envio começa na hora e a classificação aparece em seguida.
              </p>
            </>
          )}
        </label>

        {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}
      </div>

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
