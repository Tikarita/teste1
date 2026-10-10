import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ToastProvider } from "../context/ToastContext";
import NotificationCenter from "./NotificationCenter";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/clinica", label: "Clínica" },
  { to: "/radiografias", label: "Radiografias" },
  { to: "/relatorios", label: "Relatórios" }
];

export default function Layout() {
  const { user, clinic, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <ToastProvider>
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-100 flex flex-col print:hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <p className="text-lg font-semibold">AktIA</p>
          {clinic && <p className="mt-0.5 truncate text-xs text-slate-400">{clinic.name}</p>}
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
          <Link to="/privacidade" className="block hover:text-white">
            Privacidade e LGPD
          </Link>
          <span className="mt-1 block">AktIA v1.0.0</span>
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6 print:hidden">
          <span className="text-sm text-slate-500">{clinic?.name ?? "Clínica"}</span>

          <div className="flex items-center gap-4">
            <NotificationCenter />

            {user && (
              <div className="text-right leading-tight">
                <p className="text-sm font-medium text-slate-700">{user.full_name}</p>
                <p className="text-xs text-slate-400">{user.email}</p>
              </div>
            )}

            <button
              onClick={handleLogout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Sair
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 print:p-0">
          <Outlet />
        </main>
      </div>
    </div>
    </ToastProvider>
  );
}
