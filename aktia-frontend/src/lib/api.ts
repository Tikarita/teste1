import type { AnalysisResult, Clinic, Radiograph, StaffMember } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const ROOT_URL = API_URL.replace(/\/api\/v1\/?$/, "");

export class ApiError extends Error {}

async function request<T>(path: string, options?: RequestInit, baseUrl = API_URL): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: options?.body instanceof FormData
      ? undefined
      : { "Content-Type": "application/json" },
    ...options
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Erro ${response.status} ao chamar ${path}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health", undefined, ROOT_URL),
  databaseTest: () => request<{ message: string; data: unknown }>("/system/database-test"),

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
