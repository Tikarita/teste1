import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import type { Clinic } from "../lib/types";

interface ClinicContextValue {
  clinics: Clinic[];
  selectedClinicId: string | null;
  setSelectedClinicId: (id: string | null) => void;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const ClinicContext = createContext<ClinicContextValue | null>(null);

export function ClinicProvider({ children }: { children: ReactNode }) {
  const [clinics, setClinics] = useState<Clinic[]>([]);
  const [selectedClinicId, setSelectedClinicIdState] = useState<string | null>(
    () => localStorage.getItem("aktia:selectedClinicId")
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);

    api
      .listClinics()
      .then((res) => {
        setClinics(res.data);
        if (!selectedClinicId && res.data.length > 0) {
          setSelectedClinicId(res.data[0].id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar clínicas"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  function setSelectedClinicId(id: string | null) {
    setSelectedClinicIdState(id);
    if (id) {
      localStorage.setItem("aktia:selectedClinicId", id);
    } else {
      localStorage.removeItem("aktia:selectedClinicId");
    }
  }

  return (
    <ClinicContext.Provider
      value={{
        clinics,
        selectedClinicId,
        setSelectedClinicId,
        loading,
        error,
        refresh: () => setReloadToken((t) => t + 1)
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
