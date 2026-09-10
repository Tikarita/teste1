import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, setAuthToken } from "../lib/api";
import type { AuthSession, Clinic, StaffMember } from "../lib/types";

const STORAGE_KEY = "aktia:session";

interface AuthContextValue {
  user: StaffMember | null;
  clinic: Clinic | null;
  isAuthenticated: boolean;
  /** true enquanto a sessão salva ainda está sendo revalidada no backend. */
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    clinic_name: string;
    cnpj: string;
    admin_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [initializing, setInitializing] = useState(true);

  function setSession(next: AuthSession | null) {
    setSessionState(next);
    setAuthToken(next?.access_token ?? null);

    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  // Revalida a sessão salva antes de liberar as rotas protegidas: o access
  // token do Supabase expira em ~1h, então o que está no localStorage pode
  // já estar morto. Se estiver, tenta renovar pelo refresh token.
  useEffect(() => {
    const stored = readStoredSession();

    if (!stored) {
      setInitializing(false);
      return;
    }

    setAuthToken(stored.access_token);

    api
      .me()
      .then((res) => {
        setSession({ ...stored, user: res.user, clinic: res.clinic });
      })
      .catch(async () => {
        try {
          const renewed = await api.refreshSession(stored.refresh_token);
          setSession(renewed);
        } catch {
          setSession(null);
        }
      })
      .finally(() => setInitializing(false));
  }, []);

  async function login(email: string, password: string) {
    const result = await api.login({ email, password });
    setSession(result);
  }

  async function register(payload: {
    clinic_name: string;
    cnpj: string;
    admin_name: string;
    email: string;
    password: string;
  }) {
    const result = await api.register(payload);
    setSession(result);
  }

  async function logout() {
    try {
      await api.logout();
    } catch (err) {
      // Sessão já inválida no servidor não impede o logout local.
      if (!(err instanceof ApiError)) throw err;
    } finally {
      setSession(null);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        clinic: session?.clinic ?? null,
        isAuthenticated: session !== null,
        initializing,
        login,
        register,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
