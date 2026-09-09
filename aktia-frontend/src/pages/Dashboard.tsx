import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useClinics } from "../context/ClinicContext";
import type { Radiograph, StaffMember } from "../lib/types";

type ApiStatus = "checking" | "online" | "offline";

export default function Dashboard() {
  const { clinics, selectedClinicId } = useClinics();
  const activeClinic = clinics.find((c) => c.id === selectedClinicId) ?? null;

  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [dbStatus, setDbStatus] = useState<ApiStatus>("checking");
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [radiographs, setRadiographs] = useState<Radiograph[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.health().then(() => setApiStatus("online")).catch(() => setApiStatus("offline"));
    api.databaseTest().then(() => setDbStatus("online")).catch(() => setDbStatus("offline"));
  }, []);

  useEffect(() => {
    if (!selectedClinicId) {
      setStaff([]);
      setRadiographs([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    Promise.all([
      api.listStaffByClinic(selectedClinicId).then((res) => res.data).catch(() => []),
      api.listRadiographsByClinic(selectedClinicId).then((res) => res.data).catch(() => [])
    ]).then(([staffData, radiographData]) => {
      setStaff(staffData);
      setRadiographs(radiographData);
      setLoading(false);
    });
  }, [selectedClinicId]);

  const analyzed = radiographs.filter((r) => r.analysis_result);
  const adequate = analyzed.filter((r) => r.analysis_result?.efficientnet.is_adequate);
  const needsAttention = analyzed.filter((r) => !r.analysis_result?.efficientnet.is_adequate);

  const findingCounts = new Map<string, { label: string; count: number }>();
  for (const r of analyzed) {
    for (const f of r.analysis_result?.yolo.findings ?? []) {
      const entry = findingCounts.get(f.class_code) ?? { label: f.label, count: 0 };
      entry.count += 1;
      findingCounts.set(f.class_code, entry);
    }
  }
  const topFindings = [...findingCounts.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5);

  const recent = [...radiographs]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">
          {activeClinic ? activeClinic.name : "Dashboard"}
        </h1>
        <p className="text-sm text-slate-500">Visão geral dos exames e da qualidade diagnóstica da clínica.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Exames enviados" value={radiographs.length} to="/radiografias" />
        <StatCard label="Adequados para diagnóstico" value={adequate.length} to="/radiografias" tone="good" />
        <StatCard label="Precisam de atenção" value={needsAttention.length} to="/radiografias" tone="warn" />
        <StatCard label="Equipe" value={staff.length} to="/clinica" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Exames recentes</h2>

          {loading && <p className="text-sm text-slate-400">Carregando...</p>}

          {!loading && recent.length === 0 && (
            <p className="text-sm text-slate-400">Nenhum exame enviado ainda nesta clínica.</p>
          )}

          {!loading && recent.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {recent.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <Link to={`/radiografias/${r.id}`} className="font-medium text-slate-700 hover:underline">
                    {r.file_name}
                  </Link>
                  {r.analysis_result ? (
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        r.analysis_result.efficientnet.is_adequate
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-amber-200 bg-amber-50 text-amber-700"
                      }`}
                    >
                      {r.analysis_result.efficientnet.is_adequate ? "Adequado" : "Atenção"}
                    </span>
                  ) : (
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
                      Não analisado
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Achados mais comuns</h2>

          {!loading && topFindings.length === 0 && (
            <p className="text-sm text-slate-400">
              Nenhum achado registrado ainda. Analise exames em Radiografias para ver os problemas
              mais frequentes detectados pelo YOLOv8.
            </p>
          )}

          {topFindings.length > 0 && (
            <ul className="space-y-2">
              {topFindings.map(([code, { label, count }]) => (
                <li key={code} className="flex items-center justify-between text-sm">
                  <span>
                    {label} <span className="text-slate-400">({code})</span>
                  </span>
                  <span className="font-medium text-slate-700">{count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex gap-4 text-xs text-slate-400">
        <span>API: {apiStatus === "checking" ? "verificando..." : apiStatus === "online" ? "online" : "offline"}</span>
        <span>Banco: {dbStatus === "checking" ? "verificando..." : dbStatus === "online" ? "online" : "offline"}</span>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  to,
  tone
}: {
  label: string;
  value: number;
  to: string;
  tone?: "good" | "warn";
}) {
  const toneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50"
      : "border-slate-200 bg-white";

  return (
    <Link to={to} className={`rounded-lg border p-4 hover:opacity-90 ${toneClass}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </Link>
  );
}
