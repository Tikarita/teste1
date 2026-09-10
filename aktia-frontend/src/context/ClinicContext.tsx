import { createContext, useContext, type ReactNode } from "react";
import { useAuth } from "./AuthContext";
import type { Clinic } from "../lib/types";

interface ClinicContextValue {
  clinics: Clinic[];
  selectedClinicId: string | null;
  loading: boolean;
  error: string | null;
}

const ClinicContext = createContext<ClinicContextValue | null>(null);

/**
 * A clínica ativa passou a vir da sessão: cada conta pertence a uma clínica
 * (via `profiles.clinic_id`), então não há mais um seletor listando todas as
 * clínicas da base — isso exporia dados de uma clínica para outra.
 */
export function ClinicProvider({ children }: { children: ReactNode }) {
  const { clinic, initializing } = useAuth();

  return (
    <ClinicContext.Provider
      value={{
        clinics: clinic ? [clinic] : [],
        selectedClinicId: clinic?.id ?? null,
        loading: initializing,
        error: null
      }}
    >
      {children}
    </ClinicContext.Provider>
  );
}

export function useClinics() {
  const ctx = useContext(ClinicContext);
  if (!ctx) throw new Error("useClinics deve ser usado dentro de ClinicProvider");
  return ctx;
}
