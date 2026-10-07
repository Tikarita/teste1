import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { Review, ReviewReason } from "../lib/types";

export const REVIEW_REASONS: { value: ReviewReason; label: string }[] = [
  { value: "positioning", label: "Posicionamento" },
  { value: "sharpness", label: "Nitidez" },
  { value: "exposure", label: "Exposição" },
  { value: "contrast", label: "Contraste" },
  { value: "noise", label: "Ruído" },
  { value: "artifacts", label: "Artefatos" },
  { value: "coverage", label: "Cobertura anatômica" },
  { value: "framing", label: "Enquadramento" },
  { value: "other", label: "Outro motivo" }
];

const REASON_LABELS = Object.fromEntries(REVIEW_REASONS.map((r) => [r.value, r.label]));

/**
 * Decisão do profissional sobre o exame. É ela, e não a triagem da IA, que
 * entra na taxa de rejeição do relatório de qualidade.
 */
export default function ReviewCard({
  radiographId,
  review,
  onSaved
}: {
  radiographId: string;
  review: Review | null;
  onSaved: (review: Review) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [verdict, setVerdict] = useState<"adequate" | "inadequate" | null>(null);
  const [reasons, setReasons] = useState<ReviewReason[]>([]);
  const [repeated, setRepeated] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const showForm = editing || !review;
  const canSave = verdict === "adequate" || (verdict === "inadequate" && reasons.length > 0);

  function startEditing() {
    setVerdict(review?.verdict ?? null);
    setReasons((review?.reasons as ReviewReason[]) ?? []);
    setRepeated(review?.repeated ?? false);
    setNotes(review?.notes ?? "");
    setError(null);
    setEditing(true);
  }

  function toggleReason(reason: ReviewReason) {
    setReasons((current) =>
      current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason]
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!verdict || !canSave) return;

    setSaving(true);
    setError(null);

    try {
      const saved = await api.reviewRadiograph(radiographId, {
        verdict,
        reasons: verdict === "inadequate" ? reasons : [],
        repeated: verdict === "inadequate" && repeated,
        notes
      });
      onSaved(saved);
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar a revisão");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">Revisão do profissional</h3>
          <p className="text-xs text-slate-400">
            A sua decisão sobre o exame. É ela que conta na taxa de rejeição do relatório.
          </p>
        </div>
        {review && !editing && (
          <button
            onClick={startEditing}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Revisar de novo
          </button>
        )}
      </div>

      {review && !editing && (
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                review.verdict === "adequate"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-red-200 bg-red-50 text-red-700"
              }`}
            >
              {review.verdict === "adequate" ? "Adequado" : "Inadequado"}
            </span>
            {review.repeated && (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                Exame repetido
              </span>
            )}
          </div>

          {review.reasons.length > 0 && (
            <p className="text-slate-600">
              <span className="text-slate-400">Motivos:</span>{" "}
              {review.reasons.map((reason) => REASON_LABELS[reason] ?? reason).join(", ")}
            </p>
          )}
          {review.notes && <p className="whitespace-pre-wrap text-slate-600">{review.notes}</p>}

          <p className="text-xs text-slate-400">
            Revisado por {review.reviewed_by_name ?? "—"} em {new Date(review.created_at).toLocaleString("pt-BR")}
          </p>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex gap-2">
            {(["adequate", "inadequate"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setVerdict(option)}
                className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium ${
                  verdict === option
                    ? option === "adequate"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                      : "border-red-300 bg-red-50 text-red-700"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {option === "adequate" ? "Adequado" : "Inadequado"}
              </button>
            ))}
          </div>

          {verdict === "inadequate" && (
            <>
              <div>
                <p className="mb-1 text-xs font-medium text-slate-600">Motivo (marque um ou mais)</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {REVIEW_REASONS.map((reason) => (
                    <label key={reason.value} className="flex items-center gap-2 text-sm text-slate-600">
                      <input
                        type="checkbox"
                        checked={reasons.includes(reason.value)}
                        onChange={() => toggleReason(reason.value)}
                      />
                      {reason.label}
                    </label>
                  ))}
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={repeated} onChange={(e) => setRepeated(e.target.checked)} />
                O exame precisou ser repetido
              </label>
            </>
          )}

          {verdict && (
            <textarea
              value={notes}
              maxLength={2000}
              rows={2}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Observações (opcional)"
            />
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving || !canSave}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar revisão"}
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
              >
                Cancelar
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}
