import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useClinics } from "../context/ClinicContext";
import type { Radiograph, StaffMember } from "../lib/types";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrador",
  dentist: "Dentista",
  user: "Usuário"
};

export default function Clinic() {
  const { clinics, selectedClinicId } = useClinics();
  const activeClinic = clinics.find((c) => c.id === selectedClinicId) ?? null;

  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loadingStaff, setLoadingStaff] = useState(true);
  const [staffListError, setStaffListError] = useState<string | null>(null);

  const [radiographs, setRadiographs] = useState<Radiograph[]>([]);
  const [loadingRadiographs, setLoadingRadiographs] = useState(true);

  const [staffName, setStaffName] = useState("");
  const [staffEmail, setStaffEmail] = useState("");
  const [staffRole, setStaffRole] = useState("dentist");
  const [staffSubmitting, setStaffSubmitting] = useState(false);
  const [staffError, setStaffError] = useState<string | null>(null);
  const [createdCredentials, setCreatedCredentials] = useState<{ email: string; password: string } | null>(null);

  function loadStaff() {
    if (!selectedClinicId) {
      setStaff([]);
      setLoadingStaff(false);
      return;
    }

    setLoadingStaff(true);
    setStaffListError(null);

    api
      .listStaffByClinic(selectedClinicId)
      .then((res) => setStaff(res.data))
      .catch((err) => setStaffListError(err instanceof Error ? err.message : "Erro ao carregar equipe"))
      .finally(() => setLoadingStaff(false));
  }

  useEffect(loadStaff, [selectedClinicId]);

  useEffect(() => {
    if (!selectedClinicId) {
      setRadiographs([]);
      setLoadingRadiographs(false);
      return;
    }

    setLoadingRadiographs(true);
    api
      .listRadiographsByClinic(selectedClinicId)
      .then((res) => setRadiographs(res.data))
      .catch(() => setRadiographs([]))
      .finally(() => setLoadingRadiographs(false));
  }, [selectedClinicId]);

  const staffScores = staff
    .map((member) => {
      const exams = radiographs.filter((r) => r.uploaded_by === member.id);
      const analyzed = exams.filter((r) => r.analysis_result);
      const avgScore = analyzed.length
        ? Math.round(
            analyzed.reduce((sum, r) => sum + (r.analysis_result?.efficientnet.score ?? 0), 0) / analyzed.length
          )
        : null;
      const adequateCount = analyzed.filter((r) => r.analysis_result?.efficientnet.is_adequate).length;

      return { member, examCount: exams.length, analyzedCount: analyzed.length, avgScore, adequateCount };
    })
    .sort((a, b) => (b.avgScore ?? -1) - (a.avgScore ?? -1));

  async function handleAddStaff(e: FormEvent) {
    e.preventDefault();
    if (!selectedClinicId) return;

    setStaffSubmitting(true);
    setStaffError(null);
    setCreatedCredentials(null);

    try {
      const res = await api.createStaff({
        clinic_id: selectedClinicId,
        full_name: staffName,
        email: staffEmail,
        role: staffRole
      });
      setCreatedCredentials({ email: staffEmail, password: res.temporary_password });
      setStaffName("");
      setStaffEmail("");
      setStaffRole("dentist");
      loadStaff();
    } catch (err) {
      setStaffError(err instanceof ApiError ? err.message : "Erro ao adicionar funcionário");
    } finally {
      setStaffSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Clínica</h1>
        <p className="text-sm text-slate-500">Dados da clínica ativa e da equipe vinculada a ela.</p>
      </div>

      {!activeClinic ? (
        <p className="text-sm text-slate-500">Nenhuma clínica selecionada.</p>
      ) : (
        <>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Perfil da clínica</h2>
            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <div>
                <dt className="text-slate-500">Nome</dt>
                <dd className="font-medium text-slate-900">{activeClinic.name}</dd>
              </div>
              <div>
                <dt className="text-slate-500">CNPJ</dt>
                <dd className="font-medium text-slate-900">{activeClinic.cnpj}</dd>
              </div>
              {activeClinic.email && (
                <div>
                  <dt className="text-slate-500">E-mail</dt>
                  <dd className="font-medium text-slate-900">{activeClinic.email}</dd>
                </div>
              )}
            </dl>
          </div>

          <form onSubmit={handleAddStaff} className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Adicionar funcionário</h2>
            <p className="mb-3 text-xs text-slate-500">
              Cria uma conta real de acesso (Supabase Auth) vinculada a esta clínica — é o que
              permite ao funcionário enviar radiografias.
            </p>

            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Nome</label>
                <input
                  required
                  minLength={2}
                  maxLength={150}
                  value={staffName}
                  onChange={(e) => setStaffName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Dra. Maria Silva"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">E-mail</label>
                <input
                  required
                  type="email"
                  value={staffEmail}
                  onChange={(e) => setStaffEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="maria@clinica.com"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Função</label>
                <select
                  value={staffRole}
                  onChange={(e) => setStaffRole(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="dentist">Dentista</option>
                  <option value="admin">Administrador</option>
                  <option value="user">Usuário</option>
                </select>
              </div>
            </div>

            {staffError && <p className="mt-3 text-sm text-red-600">{staffError}</p>}

            <button
              type="submit"
              disabled={staffSubmitting}
              className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {staffSubmitting ? "Adicionando..." : "Adicionar funcionário"}
            </button>

            {createdCredentials && (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <p className="font-medium">Conta criada. Anote a senha temporária agora — ela não será exibida novamente.</p>
                <p className="mt-1">
                  <span className="font-medium">E-mail:</span> {createdCredentials.email}
                </p>
                <p>
                  <span className="font-medium">Senha temporária:</span>{" "}
                  <code className="rounded bg-amber-100 px-1.5 py-0.5">{createdCredentials.password}</code>
                </p>
              </div>
            )}
          </form>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Equipe ({staff.length})</h2>

            {loadingStaff && <p className="text-sm text-slate-400">Carregando...</p>}
            {staffListError && <p className="text-sm text-red-600">{staffListError}</p>}

            {!loadingStaff && !staffListError && staff.length === 0 && (
              <p className="text-sm text-slate-400">Nenhum funcionário cadastrado nesta clínica.</p>
            )}

            {!loadingStaff && staff.length > 0 && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                    <th className="pb-2">Nome</th>
                    <th className="pb-2">E-mail</th>
                    <th className="pb-2">Função</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {staff.map((member) => (
                    <tr key={member.id}>
                      <td className="py-2">{member.full_name}</td>
                      <td className="py-2 text-slate-500">{member.email}</td>
                      <td className="py-2 text-slate-500">{ROLE_LABELS[member.role] ?? member.role}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-1 text-sm font-semibold text-slate-700">Controle de qualidade por profissional</h2>
            <p className="mb-3 text-xs text-slate-500">
              Índice técnico médio (nitidez, contraste, exposição) das radiografias enviadas por cada profissional —
              mostra quem está tirando exames tecnicamente adequados para diagnóstico com consistência.
            </p>

            {(loadingStaff || loadingRadiographs) && <p className="text-sm text-slate-400">Carregando...</p>}

            {!loadingStaff && !loadingRadiographs && staff.length === 0 && (
              <p className="text-sm text-slate-400">Nenhum funcionário cadastrado nesta clínica.</p>
            )}

            {!loadingStaff && !loadingRadiographs && staffScores.length > 0 && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                    <th className="pb-2">Profissional</th>
                    <th className="pb-2">Exames enviados</th>
                    <th className="pb-2">Analisados</th>
                    <th className="pb-2">Índice médio</th>
                    <th className="pb-2">Adequados</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {staffScores.map(({ member, examCount, analyzedCount, avgScore, adequateCount }) => (
                    <tr key={member.id}>
                      <td className="py-2 font-medium">{member.full_name}</td>
                      <td className="py-2 text-slate-500">{examCount}</td>
                      <td className="py-2 text-slate-500">{analyzedCount}</td>
                      <td className="py-2">
                        {avgScore === null ? (
                          <span className="text-slate-400">—</span>
                        ) : (
                          <span
                            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                              avgScore >= 70
                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                : "border-amber-200 bg-amber-50 text-amber-700"
                            }`}
                          >
                            {avgScore} / 100
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-slate-500">
                        {analyzedCount > 0 ? `${adequateCount}/${analyzedCount}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
