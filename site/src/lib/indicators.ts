// Formatação e classes de cor por indicador (compartilhado entre build e navegador).
import { fmtBRL, fmtNumber, fmtPct, NO_DATA } from "./format";
import type { IndicatorDef, Num } from "./types";

export function fmtValue(def: Pick<IndicatorDef, "unit"> | undefined, v: Num | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  switch (def?.unit) {
    case "pct": return fmtPct(v);
    case "brl": return fmtBRL(v);
    case "brl_pc": return fmtBRL(v, 2);
    case "rate_10k": return fmtNumber(v, 1);
    case "rate_100k": return fmtNumber(v, 1);
    case "index": return fmtNumber(v, 0);
    case "lhabdia": return `${fmtNumber(v, 0)} L/hab/dia`;
    case "days": return `${fmtNumber(v, 0)} dias`;
    default: return fmtNumber(v, 0);
  }
}

export function unitLabel(def: Pick<IndicatorDef, "unit">): string {
  return ({ pct: "% da população", count: "pessoas", number: "quantidade", rate_10k: "por 10 mil habitantes", rate_100k: "por 100 mil habitantes", brl: "R$ por ano",
    brl_pc: "R$ por habitante por ano", index: "0 a 100", days: "dias por ano", lhabdia: "litros por habitante por dia",
    years: "anos", bool: "" } as Record<string, string>)[def.unit] ?? "";
}

/** Quebras por quantis (5 classes) sobre os valores presentes. */
export function quantileBreaks(values: Num[], k = 5): number[] {
  const v = values.filter((x): x is number => x !== null && !Number.isNaN(x)).sort((a, b) => a - b);
  if (v.length === 0) return [];
  const out: number[] = [];
  for (let i = 1; i < k; i++) out.push(v[Math.min(v.length - 1, Math.floor((i * v.length) / k))]);
  return [...new Set(out)];
}

export function classOf(v: Num, breaks: number[]): number | null {
  if (v === null || Number.isNaN(v)) return null;
  let c = 0;
  while (c < breaks.length && v >= breaks[c]) c++;
  return c; // 0..breaks.length
}

export const GOOD = ["#f0f9e8", "#bae4bc", "#7bccc4", "#43a2ca", "#0868ac"];
export const BAD = ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"];
export const NODATA = "#c9c4ba";

export function paletteFor(def: IndicatorDef): string[] {
  return def.direction === "higher_is_better" ? GOOD : BAD;
}

export const THERMO_LABEL: Record<string, string> = {
  atingida: "Meta atingida", no_ritmo: "No ritmo", atrasado: "Atrasado", sem_dados: "Sem dados suficientes",
};
export const THERMO_CLASS: Record<string, string> = { atingida: "ok", no_ritmo: "ok", atrasado: "alert", sem_dados: "" };
export const THERMO_COLORS: Record<string, string> = {
  atingida: "#0868ac", no_ritmo: "#43a2ca", atrasado: "#e34a33", sem_dados: NODATA,
};

export const SOURCE_LABEL: Record<string, string> = {
  ibge_censo2022: "IBGE, Censo 2022", snis: "SNIS (Ministério das Cidades)", datasus_sih: "DATASUS, SIH/SUS",
  ana_atlas_esgotos: "ANA, Atlas Esgotos", derivado: "Cálculo da plataforma", sudene_semiarido: "Sudene",
  datasus_sim: "DATASUS, SIM", sisagua: "Ministério da Saúde, SISAGUA", s2id: "MIDR, S2ID", monitor_secas: "ANA, Monitor de Secas",
  censo_escolar: "INEP, Censo Escolar", siconfi: "Tesouro Nacional, SICONFI",
};
