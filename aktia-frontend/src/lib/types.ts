export interface Clinic {
  id: string;
  name: string;
  cnpj: string;
  email?: string | null;
  created_at?: string;
}

export interface StaffMember {
  id: string;
  clinic_id: string;
  full_name: string;
  email: string;
  role: string;
  created_at?: string;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  expires_at: number | null;
  user: StaffMember;
  clinic: Clinic;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface YoloFinding {
  class_code: string;
  label: string;
  confidence: number;
  bbox: BoundingBox;
}

export interface YoloResult {
  model: string;
  findings: YoloFinding[];
}

export type QualityStatus = "approved" | "attention" | "rejected" | "pending";

export interface QualityCriterion {
  category: string;
  label: string;
  /** null quando o critério ainda não é avaliado automaticamente (status "pending"). */
  score: number | null;
  status: QualityStatus;
  /** Valor bruto da métrica de visão computacional por trás do score (ex.: variância do Laplaciano). */
  raw_value?: number | null;
}

export interface EfficientNetResult {
  model: string;
  is_adequate: boolean;
  score: number;
  criteria: QualityCriterion[];
  recommendation: string;
}

export interface AnalysisResult {
  yolo: YoloResult;
  efficientnet: EfficientNetResult;
}

export interface Radiograph {
  id: string;
  clinic_id: string;
  uploaded_by: string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  created_at?: string;
  analysis_result?: AnalysisResult | null;
}
