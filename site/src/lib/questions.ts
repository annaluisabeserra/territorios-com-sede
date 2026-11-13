// Perguntas guiadas (SPEC §6.8): lógica pura, usada no navegador e testada no Vitest.
import type { ResumoMunicipio } from "./types";

export type Mode = "ranking" | "lista" | "comparacao";
export type Filter = "todos" | "quilombolas" | "semiarido" | "pequeno" | "medio" | "grande" | "esgoto_sem_declaracao";
export interface Spec { mode: Mode; ind: string; region: string; filter: Filter; order: "desc" | "asc"; n: number; compare?: string[] }

export const FILTERS: Record<Filter, string> = {
  todos: "todos os municípios",
  quilombolas: "com população quilombola recenseada",
  semiarido: "do Semiárido",
  pequeno: "com até 20 mil habitantes",
  medio: "de 20 mil a 100 mil habitantes",
  grande: "com mais de 100 mil habitantes",
  esgoto_sem_declaracao: "sem prestador de esgoto declarado ao SNIS",
};

export function applyFilter(ms: ResumoMunicipio[], f: Filter): ResumoMunicipio[] {
  const pop = (m: ResumoMunicipio) => m.ind.populacao ?? 0;
  switch (f) {
    case "quilombolas": return ms.filter((m) => (m.ind.pop_quilombola ?? 0) > 0);
    case "semiarido": return ms.filter((m) => m.semiarido === true);
    case "pequeno": return ms.filter((m) => pop(m) <= 20_000);
    case "medio": return ms.filter((m) => pop(m) > 20_000 && pop(m) <= 100_000);
    case "grande": return ms.filter((m) => pop(m) > 100_000);
    case "esgoto_sem_declaracao": return ms.filter((m) => (m as any).esgoto_sem_declaracao === true);
    default: return ms;
  }
}

export function answer(all: ResumoMunicipio[], s: Spec): { rows: { m: ResumoMunicipio; v: number | null }[]; withoutData: number; universe: number } {
  let ms = s.region && s.region !== "todas" ? all.filter((m) => m.ri === s.region) : all;
  ms = applyFilter(ms, s.filter);
  const val = (m: ResumoMunicipio) => (s.ind === "indice_prioridade" ? m.idx : m.ind[s.ind] ?? null);
  if (s.mode === "comparacao") {
    const set = new Set(s.compare ?? []);
    const rows = all.filter((m) => set.has(m.slug)).map((m) => ({ m, v: val(m) }));
    return { rows, withoutData: rows.filter((r) => r.v === null).length, universe: rows.length };
  }
  const withV = ms.map((m) => ({ m, v: val(m) }));
  const present = withV.filter((r) => r.v !== null) as { m: ResumoMunicipio; v: number }[];
  // Empates (ex.: vários 100% autodeclarados): maior população primeiro, depois nome.
  present.sort((a, b) => (s.order === "desc" ? b.v - a.v : a.v - b.v) || (b.m.ind.populacao ?? 0) - (a.m.ind.populacao ?? 0) || a.m.nome.localeCompare(b.m.nome, "pt-BR"));
  const rows = s.mode === "ranking" ? present.slice(0, s.n) : present;
  return { rows, withoutData: withV.length - present.length, universe: withV.length };
}

export function toQuery(s: Spec): string {
  const q = new URLSearchParams({ m: s.mode, i: s.ind, r: s.region, f: s.filter, o: s.order, n: String(s.n) });
  if (s.compare?.length) q.set("c", s.compare.join(","));
  return q.toString();
}

export function fromQuery(q: URLSearchParams, d: Spec): Spec {
  const mode = (["ranking", "lista", "comparacao"] as Mode[]).includes(q.get("m") as Mode) ? (q.get("m") as Mode) : d.mode;
  const filter = (Object.keys(FILTERS) as Filter[]).includes(q.get("f") as Filter) ? (q.get("f") as Filter) : d.filter;
  const n = Math.min(100, Math.max(3, Number(q.get("n")) || d.n));
  return { mode, ind: q.get("i") ?? d.ind, region: q.get("r") ?? d.region, filter, order: q.get("o") === "asc" ? "asc" : "desc", n, compare: q.get("c")?.split(",").filter(Boolean) };
}

export const READY: { label: string; spec: Partial<Spec> }[] = [
  { label: "Quais os 10 municípios com menor atendimento de água (SNIS)?", spec: { mode: "ranking", ind: "snis_agua_pct", order: "asc", n: 10 } },
  { label: "Quais os 10 municípios com menos esgoto coletado e tratado?", spec: { mode: "ranking", ind: "snis_esgoto_tratado_pct", order: "asc", n: 10 } },
  { label: "Onde a água tratada mais se perde na distribuição?", spec: { mode: "ranking", ind: "snis_perdas_pct", order: "desc", n: 10 } },
  { label: "Municípios do Semiárido com menor atendimento de água", spec: { mode: "ranking", ind: "snis_agua_pct", order: "asc", n: 10, filter: "semiarido" } },
  { label: "Municípios com população quilombola e menor atendimento de água", spec: { mode: "ranking", ind: "snis_agua_pct", order: "asc", n: 10, filter: "quilombolas" } },
  { label: "Quais municípios não têm prestador de esgoto declarado?", spec: { mode: "lista", ind: "populacao", order: "desc", filter: "esgoto_sem_declaracao" } },
  { label: "Cidades grandes (mais de 100 mil habitantes) com menos tratamento de esgoto", spec: { mode: "ranking", ind: "snis_tratamento_pct", order: "asc", n: 10, filter: "grande" } },
  { label: "Municípios pequenos com menor coleta de lixo (Censo)", spec: { mode: "ranking", ind: "censo_lixo_coletado_pct", order: "asc", n: 10, filter: "pequeno" } },
  { label: "Onde se consome menos água por pessoa?", spec: { mode: "ranking", ind: "snis_consumo_lhabdia", order: "asc", n: 10 } },
  { label: "Municípios com maior população quilombola", spec: { mode: "ranking", ind: "pop_quilombola", order: "desc", n: 10 } },
  { label: "Municípios com maior parcela de povos quilombolas e indígenas", spec: { mode: "ranking", ind: "pct_pop_quilombola_indigena", order: "desc", n: 10 } },
  { label: "Lista de todos os municípios pelo atendimento de esgoto (SNIS)", spec: { mode: "lista", ind: "snis_esgoto_pct", order: "asc" } },
];
