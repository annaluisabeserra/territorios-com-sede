import { describe, expect, it } from "vitest";
import { answer, fromQuery, toQuery, READY, type Spec } from "./questions";

const mk = (nome: string, v: number | null, extra: any = {}) => ({ cod: nome, nome, slug: nome.toLowerCase(), ri: extra.ri ?? "A", rim: "", semiarido: extra.semi ?? false, ind: { snis_agua_pct: v, populacao: extra.pop ?? 10000, pop_quilombola: extra.q ?? null }, pct: {}, dims: {}, idx: null, rank: null, thermo: { agua: "", esgoto: "", agua_ano: null, esgoto_ano: null } } as any);
const ms = [mk("A", 50), mk("B", 90, { semi: true }), mk("C", null), mk("D", 10, { q: 30, ri: "Z" }), mk("E", 70, { pop: 200000 })];
const base: Spec = { mode: "ranking", ind: "snis_agua_pct", region: "todas", filter: "todos", order: "asc", n: 3 };

describe("perguntas guiadas", () => {
  it("ranking ignora sem dado e informa quantos faltam", () => {
    const r = answer(ms, base);
    expect(r.rows.map((x) => x.m.nome)).toEqual(["D", "A", "E"]);
    expect(r.withoutData).toBe(1);
  });
  it("filtros e região", () => {
    expect(answer(ms, { ...base, filter: "semiarido" }).rows.map((x) => x.m.nome)).toEqual(["B"]);
    expect(answer(ms, { ...base, filter: "quilombolas" }).rows.map((x) => x.m.nome)).toEqual(["D"]);
    expect(answer(ms, { ...base, region: "Z" }).rows.map((x) => x.m.nome)).toEqual(["D"]);
    expect(answer(ms, { ...base, filter: "grande" }).rows.map((x) => x.m.nome)).toEqual(["E"]);
  });
  it("comparação escolhe municípios", () => {
    expect(answer(ms, { ...base, mode: "comparacao", compare: ["a", "c"] }).rows.length).toBe(2);
  });
  it("link compartilhável ida e volta", () => {
    const s: Spec = { ...base, filter: "semiarido", order: "desc", n: 15, compare: ["a"] };
    expect(fromQuery(new URLSearchParams(toQuery(s)), base)).toEqual(s);
  });
  it("tem pelo menos 10 perguntas prontas", () => expect(READY.length).toBeGreaterThanOrEqual(10));
});

describe("fromQuery respeita a ordem padrão", () => {
  it("sem parâmetro 'o' usa a ordem do padrão; com 'o' usa a do link", async () => {
    const { fromQuery } = await import("./questions");
    const d = { mode: "ranking", ind: "snis_agua_pct", region: "todas", filter: "todos", order: "asc", n: 10 } as const;
    expect(fromQuery(new URLSearchParams(""), d as any).order).toBe("asc");
    expect(fromQuery(new URLSearchParams("o=desc"), d as any).order).toBe("desc");
  });
});
