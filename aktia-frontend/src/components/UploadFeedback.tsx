import { Link } from "react-router-dom";
import Heatmap from "./Heatmap";
import type { AnalysisResult, Radiograph } from "../lib/types";

export interface UploadOutcome {
  radiograph: Radiograph;
  status: "analyzing" | "done" | "error";
  analysis?: AnalysisResult;
  imageUrl?: string | null;
  error?: string;
}

/**
 * Retorno imediato para quem acabou de enviar a radiografia, enquanto o
 * paciente ainda está na clínica. É só um aviso da triagem da IA: não é a
 * revisão do exame nem fica registrado como feedback ao profissional.
 */
export default function UploadFeedback({ outcome, onDismiss }: { outcome: UploadOutcome; onDismiss: () => void }) {
  const { radiograph, status, analysis, imageUrl, error } = outcome;
  const quality = analysis?.efficientnet;
  const inadequate = status === "done" && quality !== undefined && !quality.is_adequate;

  const tone =
    status !== "done"
      ? "border-slate-200 bg-white"
      : inadequate
      ? "border-amber-300 bg-amber-50"
      : "border-emerald-200 bg-emerald-50";

  return (
    <div className={`rounded-lg border p-4 ${tone}`} role="status">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Radiografia enviada</p>
          <p className="text-sm font-medium text-slate-800">{radiograph.file_name}</p>
        </div>
        <button onClick={onDismiss} className="text-xs text-slate-500 hover:underline">
          Fechar
        </button>
      </div>

      {status === "analyzing" && (
        <p className="mt-3 text-sm text-slate-600">Analisando a qualidade da imagem... leva alguns segundos.</p>
      )}

      {status === "error" && (
        <p className="mt-3 text-sm text-red-600">
          A radiografia foi enviada, mas a análise não pôde ser feita agora: {error} Você pode analisá-la depois
          em{" "}
          <Link to={`/radiografias/${radiograph.id}`} className="underline">
            Ver detalhes
          </Link>
          .
        </p>
      )}

      {status === "done" && quality && (
        <div className="mt-3 grid gap-4 md:grid-cols-[minmax(0,18rem)_1fr]">
          {imageUrl && (
            <div className="relative self-start">
              <img src={imageUrl} alt={radiograph.file_name} className="w-full rounded-md" />
              {inadequate && quality.explanation && <Heatmap grid={quality.explanation.grid} />}
            </div>
          )}

          <div className="space-y-2 text-sm">
            {inadequate ? (
              <>
                <p className="text-base font-semibold text-amber-800">
                  A IA apontou possível problema de qualidade
                </p>
                <p className="text-slate-700">
                  Confira a imagem antes de liberar o paciente. Se ela realmente não servir para diagnóstico,
                  este é o melhor momento para avaliar a repetição.
                </p>
                {quality.explanation && imageUrl && (
                  <p className="text-xs text-slate-600">
                    As áreas em vermelho na imagem foram as que mais pesaram na decisão da IA.
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="text-base font-semibold text-emerald-800">A IA considerou a imagem adequada</p>
                <p className="text-slate-700">Nenhum problema de qualidade apontado na triagem.</p>
              </>
            )}

            <p className="text-slate-600">
              Probabilidade de adequação: <span className="font-medium">{quality.score} / 100</span>
            </p>

            <p className="text-xs text-slate-500">
              É uma triagem automática e pode errar nos dois sentidos: marca como inadequada cerca de 1 em cada
              8 imagens boas e deixa passar parte das ruins. A decisão é do profissional, e este aviso não fica
              registrado como avaliação do exame.
            </p>

            <Link
              to={`/radiografias/${radiograph.id}${inadequate ? "?mapa=1" : ""}`}
              className="inline-block rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            >
              Abrir exame
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
