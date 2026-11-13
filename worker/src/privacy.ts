// Normalização e higiene dos eventos: nada que identifique pessoas chega ao banco nem ao relatório.
export const TYPES = new Set(["search_no_result", "guided_question", "calc_scenario"]);

const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]+/g;
// Dígitos separados por ponto, hífen, barra ou espaço (CPF, RG, telefone, CEP) são juntados antes de mascarar.
const DIGIT_GROUPS = /\d(?:[\d.\-/\s]*\d)?/g;

export function cleanKey(type: string, data: unknown): string | null {
  if (!TYPES.has(type) || typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  const parts = Object.keys(d).sort().slice(0, 4).map((k) => `${k}=${String(d[k]).slice(0, 60)}`);
  let key = parts.join("&").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(EMAIL, "[email]");
  // Qualquer número com 3 dígitos ou mais vira "#" (anos e valores curtos de parâmetros, como 25 ou 50, ficam)
  key = key.replace(DIGIT_GROUPS, (m) => (m.replace(/\D/g, "").length >= 3 ? "#" : m));
  key = key.replace(/[^\w=&#[\] .,-]/g, "").replace(/\s+/g, " ").trim();
  return key.length ? key.slice(0, 120) : null;
}

/** Limiar k: o relatório só mostra termos buscados por pelo menos K vezes no mês (protege buscas únicas). */
export const K_ANONYMITY = 5;

export function month(d = new Date()): string {
  return d.toISOString().slice(0, 7);
}
