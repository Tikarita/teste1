// Uma cor fixa por tipo de achado: a mesma classe tem a mesma cor na tela do
// exame e no pré-laudo impresso.
const CLASS_COLORS: Record<string, string> = {
  OBT: "#3b82f6",
  END: "#a855f7",
  IMP: "#06b6d4",
  PRR: "#f97316",
  IMT: "#10b981",
  CAR: "#ef4444",
  API: "#e11d48",
  BON: "#f59e0b",
  ROT: "#84cc16",
  FUR: "#d946ef",
  APS: "#14b8a6",
  ROR: "#f43f5e",
  ORD: "#64748b",
  SRD: "#0ea5e9"
};

export function colorFor(classCode: string) {
  return CLASS_COLORS[classCode] ?? "#64748b";
}
