/** Formatação brasileira de números (SPEC §8): R$ 1.234,56; 12,5%. `null` vira "sem dado". */
export const NO_DATA = "sem dado";

const nf = (min: number, max: number) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max });

export function fmtNumber(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  return nf(digits, digits).format(v);
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  return `${nf(digits, digits).format(v)}%`;
}

export function fmtBRL(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  return `R$ ${nf(digits, digits).format(v)}`;
}

/** Valor monetário abreviado para títulos: R$ 12,3 milhões. */
export function fmtBRLShort(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  const abs = Math.abs(v);
  if (abs >= 1e9) return `R$ ${nf(1, 1).format(v / 1e9)} bilhões`;
  if (abs >= 1e6) return `R$ ${nf(1, 1).format(v / 1e6)} milhões`;
  if (abs >= 1e3) return `R$ ${nf(0, 0).format(v / 1e3)} mil`;
  return fmtBRL(v);
}

/** Data ISO → dd/mm/aaaa. Ausente ou inválida vira "sem dado". */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return NO_DATA;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? NO_DATA : d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

/** "1 em cada 3" a partir de um percentual (só para frações legíveis). */
export function oneInN(pct: number | null | undefined): string | null {
  if (pct === null || pct === undefined || pct <= 0 || pct > 100) return null;
  const n = Math.round(100 / pct);
  if (n < 2 || n > 20) return null;
  return `1 em cada ${n}`;
}

/** "da Bahia" / "do Ceará" / "de Pernambuco" a partir da preposição do `ufs.yaml`. */
export function deUF(nome: string, prep?: string | null): string {
  return `${prep || "de"} ${nome}`;
}

/** "na Bahia" / "no Ceará" / "em Pernambuco". */
export function emUF(nome: string, prep?: string | null): string {
  return `${({ da: "na", do: "no" } as Record<string, string>)[prep ?? ""] ?? "em"} ${nome}`;
}
