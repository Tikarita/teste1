import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

export interface Toast {
  /** Reusar a mesma chave substitui o aviso anterior (ex.: "analisando" vira o resultado). */
  key: string;
  tone: "info" | "success" | "danger";
  title: string;
  message?: string;
  link?: { to: string; label: string };
  action?: { label: string; onClick: () => void };
  /** Some sozinho depois desse tempo. Sem valor, fica até ser fechado. */
  autoCloseMs?: number;
}

interface ToastContextValue {
  showToast: (toast: Toast) => void;
  dismissToast: (key: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_STYLES: Record<Toast["tone"], string> = {
  info: "border-slate-300 bg-white",
  success: "border-emerald-300 bg-emerald-50",
  danger: "border-red-400 bg-red-50"
};

/** Avisos empilhados no canto inferior direito da tela. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, number>());

  const dismissToast = useCallback((key: string) => {
    window.clearTimeout(timers.current.get(key));
    timers.current.delete(key);
    setToasts((current) => current.filter((toast) => toast.key !== key));
  }, []);

  const showToast = useCallback(
    (toast: Toast) => {
      window.clearTimeout(timers.current.get(toast.key));
      timers.current.delete(toast.key);
      setToasts((current) => [...current.filter((item) => item.key !== toast.key), toast]);

      if (toast.autoCloseMs) {
        timers.current.set(toast.key, window.setTimeout(() => dismissToast(toast.key), toast.autoCloseMs));
      }
    },
    [dismissToast]
  );

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}

      <div className="fixed bottom-4 right-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-3 print:hidden">
        {toasts.map((toast) => (
          <div
            key={toast.key}
            role={toast.tone === "danger" ? "alert" : "status"}
            className={`rounded-lg border-2 p-4 shadow-lg ${TONE_STYLES[toast.tone]}`}
          >
            <div className="flex items-start justify-between gap-3">
              <p className={`text-sm font-semibold ${toast.tone === "danger" ? "text-red-800" : "text-slate-800"}`}>
                {toast.title}
              </p>
              <button
                onClick={() => dismissToast(toast.key)}
                aria-label="Fechar aviso"
                className="text-slate-400 hover:text-slate-600"
              >
                ×
              </button>
            </div>

            {toast.message && <p className="mt-1 text-sm text-slate-700">{toast.message}</p>}

            {(toast.link || toast.action) && (
              <div className="mt-3 flex gap-2">
                {toast.link && (
                  <Link
                    to={toast.link.to}
                    onClick={() => dismissToast(toast.key)}
                    className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
                  >
                    {toast.link.label}
                  </Link>
                )}
                {toast.action && (
                  <button
                    onClick={() => {
                      toast.action?.onClick();
                      dismissToast(toast.key);
                    }}
                    className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700"
                  >
                    {toast.action.label}
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToasts() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToasts deve ser usado dentro de ToastProvider");
  return ctx;
}
