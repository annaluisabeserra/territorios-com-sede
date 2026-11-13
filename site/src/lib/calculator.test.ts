import { describe, expect, it } from "vitest";
import parity from "./calculator.parity.json";
import { calculate, sensitivity, fromQuery, toQuery, DEFAULT_PARAMS, type Params } from "./calculator";

const cases = parity.cases as any[];
const ranges = parity.ranges as any;

describe("paridade exata Python × TypeScript", () => {
  it("tem casos gerados pelo Python", () => expect(cases.length).toBeGreaterThan(200));
  for (const [i, c] of cases.entries()) {
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
      expect(sensitivity(c.baseline, c.params, ranges)).toEqual(c.sensitivity);
    });
  }
});

describe("link compartilhável", () => {
  it("ida e volta pela URL preserva os parâmetros", () => {
    const p: Params = { ...DEFAULT_PARAMS, reduction_pct: 92, horizon_years: 15, investment: 1e6, deadweight: 0.1, attribution: 0.8, drop_off: 0.05, use_outpatient: true, outpatient_multiplier: 1.5, use_deaths: true };
    const back = fromQuery(new URLSearchParams(toQuery(p)));
    expect(back).toEqual(p);
  });
  it("parâmetro vazio não vira zero", () => {
    expect(fromQuery(new URLSearchParams("r=&h=")).reduction_pct).toBe(DEFAULT_PARAMS.reduction_pct);
  });
  it("faixa de sensibilidade sempre contém o valor central", () => {
    const b = { hospital_cost: 1e5, hospital_days: 1e3, school_days: 10, daily_income: 50 };
    for (const t of [0, 0.02, 0.085, 0.15, 0.3]) {
      const p = { ...DEFAULT_PARAMS, discount_rate: t };
      const s = sensitivity(b, p, ranges);
      const c = calculate(b, p).pv_saving;
      expect(s.pv[0] <= c && c <= s.pv[1]).toBe(true);
    }
  });
  it("limita valores fora da faixa", () => {
    const p = fromQuery(new URLSearchParams("r=500&h=99&t=-1"));
    expect(p.reduction_pct).toBe(100);
    expect(p.horizon_years).toBe(30);
    expect(p.discount_rate).toBe(0);
  });
});
