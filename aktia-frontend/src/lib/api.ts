import type { AnalysisResult, AuthSession, Clinic, Radiograph, StaffMember } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const ROOT_URL = API_URL.replace(/\/api\/v1\/?$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/**
 * Token mantido em módulo, e não importado do AuthContext, para evitar
 * dependência circular (o contexto já importa este arquivo).
 */
let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

async function request<T>(path: string, options?: RequestInit, baseUrl = API_URL): Promise<T> {
  const headers: Record<string, string> = {};

  if (!(options?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string> | undefined) }
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(detail ?? `Erro ${response.status} ao chamar ${path}`, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health", undefined, ROOT_URL),
  databaseTest: () => request<{ message: string; data: unknown }>("/system/database-test"),

  register: (payload: {
    clinic_name: string;
    cnpj: string;
    admin_name: string;
    email: string;
    password: string;
  }) =>
    request<AuthSession>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  login: (payload: { email: string; password: string }) =>
    request<AuthSession>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  me: () => request<{ user: StaffMember; clinic: Clinic }>("/auth/me"),
  refreshSession: (refreshToken: string) =>
    request<AuthSession>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken })
    }),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),

  listClinics: () => request<{ data: Clinic[] }>("/clinics/"),
  createClinic: (payload: { name: string; cnpj: string }) =>
    request<{ message: string; data: Clinic[] }>("/clinics/", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  listStaffByClinic: (clinicId: string) =>
    request<{ data: StaffMember[] }>(`/staff/clinic/${clinicId}`),
  createStaff: (payload: { clinic_id: string; full_name: string; email: string; role: string }) =>
    request<{ message: string; data: StaffMember; temporary_password: string }>("/staff/", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  listRadiographsByClinic: (clinicId: string) =>
    request<{ data: Radiograph[] }>(`/analysis/clinic/${clinicId}`),
  getRadiograph: (id: string) =>
    request<{ data: Radiograph; signed_url: Record<string, string> }>(`/analysis/${id}`),
  uploadRadiograph: (payload: { clinic_id: string; uploaded_by: string; file: File }) => {
    const formData = new FormData();
    formData.append("clinic_id", payload.clinic_id);
    formData.append("uploaded_by", payload.uploaded_by);
    formData.append("file", payload.file);

    return request<{ message: string; data: Radiograph[] }>("/analysis/upload", {
      method: "POST",
      body: formData
    });
  },
  analyzeRadiograph: (id: string) =>
    request<{ data: AnalysisResult }>(`/analysis/${id}/analyze`, { method: "POST" }),
  deleteRadiograph: (id: string) =>
    request<{ message: string; id: string }>(`/analysis/${id}`, { method: "DELETE" })
};
