export interface Clinic {
  id: string;
  name: string;
  cnpj: string;
  email?: string | null;
  created_at?: string;
}

/** Os papéis aceitos pelo banco (constraint profiles_role_check). */
export type StaffRole = "admin" | "manager" | "user";

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
  /** true nas classes em que o detector teve desempenho fraco no teste. */
  low_reliability?: boolean;
  bbox: BoundingBox;
}

export interface YoloResult {
  model: string | null;
  /**
   * true quando os achados vieram do modelo treinado. Quando é false ou está
   * ausente, `findings` vazio significa "não avaliado", não "nada encontrado":
   * análises antigas não têm o campo, e seus achados vinham de um placeholder
   * que não deve ser exibido.
   */
  available?: boolean;
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
  /** Probabilidade de "adequado" (0-100) segundo o classificador; 50 é a fronteira da decisão. */
  score: number;
  /** Probabilidade (0-1) da classe escolhida. Ausente em análises feitas antes do modelo supervisionado. */
  confidence?: number;
  /**
   * Grad-CAM da classe escolhida: grade de valores 0-1 cobrindo a imagem
   * inteira. Ausente em análises feitas antes de a explicação existir.
   */
  explanation?: {
    method: string;
    target_class: string;
    grid: number[][];
  };
  /**
   * Vazio nas análises novas: os critérios automáticos de imagem foram
   * descontinuados por não se relacionarem com a adequação. Análises antigas
   * ainda trazem a lista, que não é mais exibida.
   */
  criteria: QualityCriterion[];
  /** Medidas brutas da imagem, só informativas (sem nota nem status). */
  image_measurements?: { key: string; label: string; value: number }[];
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
  /** Profissional responsável pela captura. null em radiografias antigas. */
  professional_id?: string | null;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  created_at?: string;
  analysis_result?: AnalysisResult | null;
}

// --- Estatísticas (/stats/*) -------------------------------------------------
// Valores numéricos chegam prontos do backend. null + insufficient_data
// significa "sem dados suficientes", nunca zero.

export type StatsPeriod = "7" | "30" | "90";

export interface StatsQuery {
  period: StatsPeriod;
  professional_id?: string;
  status?: "approved" | "attention" | "rejected";
}

export interface StatusCounts {
  approved: number;
  attention: number;
  rejected: number;
}

export interface PeriodSummary {
  total: number;
  status_counts: StatusCounts;
  avg_score: number | null;
  status_rates: StatusCounts | null;
  insufficient_data: boolean;
}

export interface QualitySummary {
  min_sample_size: number;
  current: PeriodSummary;
  previous: PeriodSummary;
  comparison: {
    avg_score_delta: number | null;
    approved_rate_delta: number | null;
    insufficient_data: boolean;
  };
}

export interface QualityHistory {
  granularity: "day" | "week";
  min_sample_size: number;
  total: number;
  points: { bucket: string; avg_score: number | null; total: number }[] | null;
  insufficient_data: boolean;
}

export interface QualityFindingsStats {
  min_sample_size: number;
  total_analyses: number;
  total_findings: number | null;
  items: { category: string; label: string; count: number; percentage: number }[] | null;
  insufficient_data: boolean;
}

export interface ProfessionalStats {
  /** null = radiografias sem profissional informado. */
  professional_id: string | null;
  full_name: string | null;
  total: number;
  status_counts: StatusCounts;
  avg_score: number | null;
  approved_rate: number | null;
  insufficient_data: boolean;
}

export interface ProfessionalsStats {
  min_sample_size: number;
  professionals: ProfessionalStats[];
}

export interface ClinicalFindingsStats {
  min_sample_size: number;
  analyses_evaluated: number;
  items:
    | {
        class_code: string;
        label: string;
        low_reliability: boolean;
        count: number;
        analyses_with_finding: number;
        percentage_of_analyses: number;
      }[]
    | null;
  insufficient_data: boolean;
}

// --- Relatórios de Garantia da Qualidade (/reports/quality) ------------------

export interface ReportSummary {
  id: string;
  report_type: string;
  title: string | null;
  /** O período é [period_start, period_end). */
  period_start: string | null;
  period_end: string | null;
  created_at: string;
  generated_by_name: string | null;
}

export interface QualityReport extends ReportSummary {
  notes: string | null;
  /** Cópia congelada dos números na emissão. */
  data: {
    clinic: { name: string; cnpj: string | null };
    generated_by: { id: string; full_name: string | null };
    period: { start: string; end: string };
    previous_period: { start: string; end: string };
    min_sample_size: number;
    volume: { uploaded: number; analyzed: number; not_analyzed: number };
    summary: PeriodSummary;
    previous: PeriodSummary;
    comparison: QualitySummary["comparison"];
    history_granularity: "day" | "week";
    history: { bucket: string; avg_score: number | null; total: number }[] | null;
    professionals: ProfessionalStats[];
    /** Só relatórios antigos trazem esta lista; nos novos ela foi descontinuada. */
    quality_findings?: { category: string; label: string; count: number; percentage: number }[] | null;
    quality_findings_discontinued?: boolean;
    /** Ausente nos relatórios emitidos antes de existir a revisão humana. */
    review?: ReviewStats | null;
    models: { model_version: string; total: number }[];
    methodology: string[];
  };
}

// --- Revisão humana ----------------------------------------------------------

export type ReviewReason =
  | "sharpness"
  | "exposure"
  | "contrast"
  | "positioning"
  | "noise"
  | "artifacts"
  | "coverage"
  | "framing"
  | "other";

export interface Review {
  id: string;
  radiograph_id: string;
  analysis_id: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  verdict: "adequate" | "inadequate";
  repeated: boolean;
  reasons: string[];
  notes: string | null;
  created_at: string;
}

/** Taxas ficam nulas (com insufficient_data) abaixo da amostra mínima de revisões. */
export interface ReviewStats {
  uploaded: number;
  reviewed: number;
  coverage_rate: number | null;
  human_adequate: number;
  human_inadequate: number;
  repeated: number;
  rejection_rate: number | null;
  repeat_rate: number | null;
  compared_with_ai: number;
  agreed_with_ai: number;
  ai_agreement_rate: number | null;
  ai_missed: number;
  ai_false_alarm: number;
  reasons: { reason: string; label: string; count: number; percentage: number }[] | null;
  insufficient_data: boolean;
}

export interface ReviewStatsResponse extends ReviewStats {
  min_sample_size: number;
}

// --- Perfil por profissional (/stats/professionals/{id}) ---------------------

export interface ProfessionalProfile {
  professional: { id: string; full_name: string | null; role: string | null };
  min_sample_size: number;
  summary: PeriodSummary;
  previous: PeriodSummary;
  /** Período atual menos o anterior. */
  comparison: QualitySummary["comparison"];
  clinic_summary: PeriodSummary;
  /** Profissional menos a clínica. */
  versus_clinic: QualitySummary["comparison"];
  history_granularity: "day" | "week";
  history: { bucket: string; avg_score: number | null; total: number }[] | null;
  review: ReviewStats;
  clinic_rejection_rate: number | null;
}
