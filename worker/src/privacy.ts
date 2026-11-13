// Normalização e higiene dos eventos: nada que identifique pessoas chega ao banco.
export const TYPES = new Set(["search_no_result", "guided_question", "calc_scenario"]);

const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]+/g;
const DIGITS = /\d{5,}/g; // CPF, telefone, CEP e afins viram "#"

export function cleanKey(type: string, data: unknown): string | null {
  if (!TYPES.has(type) || typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  const parts = Object.keys(d).sort().slice(0, 4).map((k) => `${k}=${String(d[k]).slice(0, 60)}`);
  const key = parts.join("&").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(EMAIL, "[email]").replace(DIGITS, "#").replace(/[^\w=&#[\] .,-]/g, "").trim();
  return key.length ? key.slice(0, 120) : null;
}

export function month(d = new Date()): string {
  return d.toISOString().slice(0, 7);
}
