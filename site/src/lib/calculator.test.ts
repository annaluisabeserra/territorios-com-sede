import { describe, expect, it } from "vitest";
import cases from "./calculator.parity.json";
import { calculate, sensitivity, fromQuery, toQuery, DEFAULT_PARAMS, type Params } from "./calculator";

const ranges = { discount_rate: [0.04, 0.12], deadweight: [0, 0.3], attribution: [0.5, 1], drop_off: [0, 0.15] } as const;

describe("paridade exata Python × TypeScript", () => {
  it("tem casos gerados pelo Python", () => expect(cases.length).toBe(204));
  for (const [i, c] of (cases as any[]).entries()) {
    it(`caso ${i}`, () => {
      const r = calculate(c.baseline, c.params as Params);
      expect(r.annual_base).toBe(c.result.annual_base);
      expect(r.annual_saving).toBe(c.result.annual_saving);
      expect(r.pv_saving).toBe(c.result.pv_saving);
      expect(r.school_days_avoided).toBe(c.result.school_days_avoided);
      expect(r.sroi_pv).toBe(c.result.sroi_pv);
      expect(r.sroi_ratio).toBe(c.result.sroi_ratio);
      expect(r.components).toEqual(c.result.components);
      expect(r.missing).toEqual(c.result.missing);
      expect(sensitivity(c.baseline, c.params, ranges as any)).toEqual(c.sensitivity);
    });
  }
});

describe("link compartilhável", () => {
  it("ida e volta pela URL preserva os parâmetros", () => {
    const p: Params = { ...DEFAULT_PARAMS, reduction_pct: 92, horizon_years: 15, investment: 1e6, deadweight: 0.1, attribution: 0.8, drop_off: 0.05 };
    const back = fromQuery(new URLSearchParams(toQuery(p)));
    expect(back).toEqual(p);
  });
  it("limita valores fora da faixa", () => {
    const p = fromQuery(new URLSearchParams("r=500&h=99&t=-1"));
    expect(p.reduction_pct).toBe(100);
    expect(p.horizon_years).toBe(30);
    expect(p.discount_rate).toBe(0);
  });
});
