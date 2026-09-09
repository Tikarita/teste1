import { NavLink, Outlet } from "react-router-dom";
import { useClinics } from "../context/ClinicContext";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/clinica", label: "Clínica" },
  { to: "/radiografias", label: "Radiografias" }
];

export default function Layout() {
  const { clinics, selectedClinicId, setSelectedClinicId, loading } = useClinics();

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-100 flex flex-col">
        <div className="px-5 py-4 text-lg font-semibold border-b border-slate-800">
          AktIA
        </div>

        <nav className="flex-1 px-2 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-700 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-slate-800 text-xs text-slate-400">
          AktIA API v1.0.0
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6">
          <span className="text-sm text-slate-500">Clínica ativa</span>

          <select
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={selectedClinicId ?? ""}
            onChange={(e) => setSelectedClinicId(e.target.value || null)}
            disabled={loading || clinics.length === 0}
          >
            {clinics.length === 0 && <option value="">Nenhuma clínica cadastrada</option>}
            {clinics.map((clinic) => (
              <option key={clinic.id} value={clinic.id}>
                {clinic.name}
              </option>
            ))}
          </select>
        </header>

        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
