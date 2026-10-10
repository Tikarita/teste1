import type { ReactNode } from "react";
import { Link } from "react-router-dom";

// Data da última revisão deste texto. Atualize sempre que o conteúdo mudar.
const UPDATED_AT = "10/10/2026";

/**
 * Política de privacidade e LGPD. Página pública (não exige login), curta e
 * em linguagem simples. Descreve só o que o sistema realmente faz: se o
 * tratamento de dados mudar, este texto precisa mudar junto.
 */
export default function Privacy() {
  return (
    <div className="min-h-screen bg-slate-100 px-4 py-10">
      <main className="mx-auto max-w-2xl">
        <Link to="/login" className="text-sm text-slate-500 hover:underline">
          &larr; AktIA
        </Link>

        <article className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <header className="border-b border-slate-100 px-6 py-5">
            <h1 className="text-xl font-semibold text-slate-900">Privacidade e LGPD</h1>
            <p className="mt-1 text-sm text-slate-500">
              Como o AktIA trata os dados, em poucas linhas. Atualizado em {UPDATED_AT}.
            </p>
          </header>

          {/* Resumo: o essencial antes de qualquer detalhe */}
          <ul className="grid gap-3 border-b border-slate-100 px-6 py-5 sm:grid-cols-3">
            <Highlight title="Sem nome do paciente">
              O paciente é identificado só pelo código do prontuário da clínica.
            </Highlight>
            <Highlight title="Cada clínica vê só o seu">
              Exames e relatórios de uma clínica nunca aparecem para outra.
            </Highlight>
            <Highlight title="A IA não decide">
              Ela apoia; quem avalia e assina é sempre o profissional.
            </Highlight>
          </ul>

          <div className="divide-y divide-slate-100">
            <Topic title="Quais dados guardamos">
              <ul className="list-disc space-y-1 pl-5">
                <li>
                  <strong>Da equipe da clínica:</strong> nome, e-mail e função de quem usa o sistema, e nome, CNPJ e
                  e-mail da clínica.
                </li>
                <li>
                  <strong>Dos exames:</strong> a imagem da radiografia, o código do paciente informado pela clínica,
                  a data e os resultados da análise e da revisão.
                </li>
                <li>
                  Quando o exame chega em formato DICOM, guardamos só os dados técnicos (data, aparelho, exposição).
                  Nome, documento e data de nascimento do paciente que venham no arquivo são descartados, e o
                  arquivo original não é armazenado.
                </li>
              </ul>
            </Topic>

            <Topic title="Para que usamos">
              <p>
                Para avaliar a qualidade técnica das radiografias, apoiar o pré-laudo e manter os registros do
                Programa de Garantia da Qualidade exigido pela ANVISA (RDC nº 611/2022). Os dados não são vendidos
                nem usados para publicidade.
              </p>
            </Topic>

            <Topic title="Como protegemos">
              <ul className="list-disc space-y-1 pl-5">
                <li>Acesso só com login, e cada usuário enxerga apenas os dados da própria clínica.</li>
                <li>As imagens ficam em armazenamento privado e só abrem por links temporários.</li>
                <li>A comunicação com o sistema é criptografada (HTTPS).</li>
              </ul>
            </Topic>

            <Topic title="Por quanto tempo">
              <p>
                Os exames ficam guardados enquanto a clínica os mantiver no sistema. Relatórios e pré-laudos emitidos
                não podem ser alterados e são mantidos como registro, já que a ANVISA exige guardar a documentação
                do programa de qualidade por pelo menos 5 anos.
              </p>
            </Topic>

            <Topic title="Seus direitos">
              <p>
                Pela LGPD (Lei nº 13.709/2018), você pode pedir para confirmar se temos dados seus, acessá-los,
                corrigi-los, saber com quem são compartilhados e solicitar a eliminação quando a lei permitir.
              </p>
              <p className="mt-2">
                <strong>Pacientes:</strong> a responsável pelos seus dados é a clínica onde você fez o exame. Faça o
                pedido diretamente a ela, que encaminhará ao AktIA quando necessário.
              </p>
            </Topic>
          </div>

          <footer className="border-t border-slate-100 bg-slate-50 px-6 py-4 text-xs text-slate-500">
            Dúvidas sobre privacidade: fale com a clínica responsável pelo seu atendimento.
          </footer>
        </article>
      </main>
    </div>
  );
}

function Highlight({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className="rounded-lg bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{children}</p>
    </li>
  );
}

function Topic({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group px-6 py-4">
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-slate-800">
        {title}
        <span className="text-slate-400 transition-transform group-open:rotate-45">+</span>
      </summary>
      <div className="mt-3 text-sm leading-relaxed text-slate-600">{children}</div>
    </details>
  );
}
