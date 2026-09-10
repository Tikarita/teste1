import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

type Tab = "login" | "register";

export default function Login() {
  const { isAuthenticated, initializing, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [tab, setTab] = useState<Tab>("login");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [clinicName, setClinicName] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [adminName, setAdminName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  if (!initializing && isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  function switchTab(next: Tab) {
    setTab(next);
    setError(null);
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(loginEmail, loginPassword);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Verifique se a API está online.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();

    if (registerPassword !== confirmPassword) {
      setError("As senhas não coincidem.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await register({
        clinic_name: clinicName,
        cnpj,
        admin_name: adminName,
        email: registerEmail,
        password: registerPassword
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Não foi possível cadastrar. Verifique se a API está online."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold text-slate-900">AktIA</h1>
          <p className="mt-1 text-sm text-slate-500">
            Análise de radiografias odontológicas para clínicas.
          </p>
        </div>

        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-2 border-b border-slate-200">
            <TabButton active={tab === "login"} onClick={() => switchTab("login")}>
              Entrar
            </TabButton>
            <TabButton active={tab === "register"} onClick={() => switchTab("register")}>
              Cadastrar clínica
            </TabButton>
          </div>

          <div className="p-6">
            {tab === "login" ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <Field label="E-mail">
                  <input
                    required
                    type="email"
                    autoComplete="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    className={inputClass}
                    placeholder="clinica@exemplo.com"
                  />
                </Field>

                <Field label="Senha">
                  <input
                    required
                    type="password"
                    autoComplete="current-password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className={inputClass}
                    placeholder="••••••••"
                  />
                </Field>

                {error && <p className="text-sm text-red-600">{error}</p>}

                <button type="submit" disabled={submitting} className={submitClass}>
                  {submitting ? "Entrando..." : "Entrar"}
                </button>

                <p className="text-center text-xs text-slate-500">
                  Ainda não tem conta?{" "}
                  <button
                    type="button"
                    onClick={() => switchTab("register")}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    Cadastre sua clínica
                  </button>
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <p className="text-xs text-slate-500">
                  O cadastro cria a clínica e a conta de administrador dela. Depois, adicione a
                  equipe na aba Clínica.
                </p>

                <Field label="Nome da clínica">
                  <input
                    required
                    minLength={2}
                    maxLength={150}
                    value={clinicName}
                    onChange={(e) => setClinicName(e.target.value)}
                    className={inputClass}
                    placeholder="Clínica Sorriso"
                  />
                </Field>

                <Field label="CNPJ">
                  <input
                    required
                    minLength={14}
                    maxLength={18}
                    value={cnpj}
                    onChange={(e) => setCnpj(e.target.value)}
                    className={inputClass}
                    placeholder="00.000.000/0000-00"
                  />
                </Field>

                <Field label="Nome do administrador">
                  <input
                    required
                    minLength={2}
                    maxLength={150}
                    value={adminName}
                    onChange={(e) => setAdminName(e.target.value)}
                    className={inputClass}
                    placeholder="Dra. Maria Silva"
                  />
                </Field>

                <Field label="E-mail de acesso">
                  <input
                    required
                    type="email"
                    autoComplete="email"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    className={inputClass}
                    placeholder="maria@clinica.com"
                  />
                </Field>

                <Field label="Senha">
                  <input
                    required
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    className={inputClass}
                    placeholder="Mínimo de 8 caracteres"
                  />
                </Field>

                <Field label="Confirmar senha">
                  <input
                    required
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className={inputClass}
                    placeholder="Repita a senha"
                  />
                </Field>

                {error && <p className="text-sm text-red-600">{error}</p>}

                <button type="submit" disabled={submitting} className={submitClass}>
                  {submitting ? "Cadastrando..." : "Cadastrar clínica"}
                </button>

                <p className="text-center text-xs text-slate-500">
                  Já tem conta?{" "}
                  <button
                    type="button"
                    onClick={() => switchTab("login")}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    Entrar
                  </button>
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const inputClass = "w-full rounded-md border border-slate-300 px-3 py-2 text-sm";
const submitClass =
  "w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50";

function TabButton({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-3 text-sm font-medium transition-colors ${
        active
          ? "bg-white text-slate-900"
          : "bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      {children}
    </div>
  );
}
