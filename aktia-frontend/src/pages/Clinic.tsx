import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useClinics } from "../context/ClinicContext";
import { useAuth } from "../context/AuthContext";
import type { ProfessionalsStats, StaffMember, StaffRole } from "../lib/types";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrador",
  manager: "Gestor",
  user: "Profissional"
};

const STATS_PERIOD = "90";

export default function Clinic() {
  const { clinics, selectedClinicId } = useClinics();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const activeClinic = clinics.find((c) => c.id === selectedClinicId) ?? null;

  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loadingStaff, setLoadingStaff] = useState(true);
  const [staffListError, setStaffListError] = useState<string | null>(null);

  const [professionalStats, setProfessionalStats] = useState<ProfessionalsStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [staffName, setStaffName] = useState("");
  const [staffEmail, setStaffEmail] = useState("");
  const [staffRole, setStaffRole] = useState<StaffRole>("user");
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

  // Médias e taxas por profissional vêm prontas do backend (/stats/professionals).
  useEffect(() => {
    if (!selectedClinicId) {
      setProfessionalStats(null);
      setLoadingStats(false);
      return;
    }

    setLoadingStats(true);
    setStatsError(null);
    api
      .statsProfessionals({ period: STATS_PERIOD })
      .then(setProfessionalStats)
      .catch((err) => setStatsError(err instanceof Error ? err.message : "Erro ao carregar estatísticas"))
      .finally(() => setLoadingStats(false));
  }, [selectedClinicId, staff.length]);

  async function handleAddStaff(e: FormEvent) {
    e.preventDefault();
    if (!selectedClinicId) return;

    setStaffSubmitting(true);
    setStaffError(null);
    setCreatedCredentials(null);

    try {
      const res = await api.createStaff({
        full_name: staffName,
        email: staffEmail,
        role: staffRole
      });
      setCreatedCredentials({ email: staffEmail, password: res.temporary_password });
      setStaffName("");
      setStaffEmail("");
      setStaffRole("user");
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

          {isAdmin && (
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
                  onChange={(e) => setStaffRole(e.target.value as StaffRole)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="user">Profissional</option>
                  <option value="manager">Gestor</option>
                  <option value="admin">Administrador</option>
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
          )}

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
              Radiografias analisadas nos últimos {STATS_PERIOD} dias, por profissional responsável pela captura.
              O score é a probabilidade de adequação segundo o classificador. Média e taxa só aparecem a partir
              de {professionalStats?.min_sample_size ?? 5} análises.
            </p>

            {loadingStats && <p className="text-sm text-slate-400">Carregando...</p>}
            {statsError && <p className="text-sm text-red-600">{statsError}</p>}

            {!loadingStats && professionalStats && professionalStats.professionals.length === 0 && (
              <p className="text-sm text-slate-400">Nenhum funcionário cadastrado nesta clínica.</p>
            )}

            {!loadingStats && professionalStats && professionalStats.professionals.length > 0 && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                    <th className="pb-2">Profissional</th>
                    <th className="pb-2">Analisadas</th>
                    <th className="pb-2">Score médio</th>
                    <th className="pb-2">Adequadas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {professionalStats.professionals.map((row) => (
                    <tr key={row.professional_id ?? "sem-profissional"}>
                      <td className="py-2 font-medium">
                        {row.professional_id === null ? (
                          <span className="font-normal text-slate-500">Sem profissional informado</span>
                        ) : isAdmin || user?.role === "manager" || row.professional_id === user?.id ? (
                          <Link to={`/profissionais/${row.professional_id}`} className="hover:underline">
                            {row.full_name ?? "Profissional"}
                          </Link>
                        ) : (
                          row.full_name
                        )}
                      </td>
                      <td className="py-2 text-slate-500">{row.total}</td>
                      <td className="py-2">
                        {row.avg_score === null ? (
                          <span className="text-xs text-slate-400">
                            {row.total === 0 ? "—" : "dados insuficientes"}
                          </span>
                        ) : (
                          <span className="font-medium text-slate-700">{row.avg_score.toFixed(1)} / 100</span>
                        )}
                      </td>
                      <td className="py-2 text-slate-500">
                        {row.total === 0
                          ? "—"
                          : `${row.status_counts.approved}/${row.total}` +
                            (row.approved_rate !== null ? ` (${row.approved_rate.toFixed(1)}%)` : "")}
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
