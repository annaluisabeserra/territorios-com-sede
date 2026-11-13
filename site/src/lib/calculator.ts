/**
 * Calculadora de economia / SROI (SPEC §6.4). Espelho exato de pipeline/transform/calculator.py.
 * Regras de paridade: sem Math.pow, fatores iterativos, mesma ordem de somas, nenhum arredondamento interno.
 * Testada contra casos gerados pelo Python em calculator.parity.json (paridade bit a bit).
 */
import type { Baseline } from "./types";

export interface Params {
  reduction_pct: number;
  horizon_years: number;
  discount_rate: number;
  use_hospital: boolean;
  use_productivity: boolean;
  use_outpatient: boolean;
  outpatient_multiplier: number;
  use_deaths: boolean;
  investment: number | null;
  deadweight: number;
  attribution: number;
  drop_off: number;
}

export const DEFAULT_PARAMS: Params = {
  reduction_pct: 50, horizon_years: 10, discount_rate: 0.085, use_hospital: true, use_productivity: true,
  use_outpatient: false, outpatient_multiplier: 0, use_deaths: false, investment: null, deadweight: 0,
  attribution: 1, drop_off: 0,
};

export interface Result {
  annual_base: number;
  components: Record<string, number>;
  annual_saving: number;
  pv_saving: number;
  school_days_avoided: number | null;
  sroi_pv: number | null;
  sroi_ratio: number | null;
  missing: string[];
}

function validate(p: Params): void {
  if (!(p.reduction_pct >= 0 && p.reduction_pct <= 100)) throw new RangeError("reduction_pct deve estar entre 0 e 100");
  if (!(p.horizon_years >= 1 && p.horizon_years <= 30)) throw new RangeError("horizon_years deve estar entre 1 e 30");
  if (p.discount_rate < 0) throw new RangeError("discount_rate não pode ser negativa");
  for (const k of ["deadweight", "attribution", "drop_off"] as const) {
    if (!(p[k] >= 0 && p[k] <= 1)) throw new RangeError(`${k} deve estar entre 0 e 1`);
  }
}

const isNum = (v: number | null | undefined): v is number => v !== null && v !== undefined && !Number.isNaN(v);

export function components(b: Baseline, p: Params): { comp: Record<string, number>; missing: string[] } {
  const comp: Record<string, number> = {};
  const missing: string[] = [];
  if (p.use_hospital) {
    if (!isNum(b.hospital_cost)) missing.push("hospital");
    else comp.hospital = b.hospital_cost;
  }
  if (p.use_productivity) {
    if (!isNum(b.hospital_days) || !isNum(b.daily_income)) missing.push("productivity");
    else comp.productivity = b.hospital_days * b.daily_income;
  }
  if (p.use_outpatient) {
    if (!isNum(b.hospital_cost) || p.outpatient_multiplier <= 0) missing.push("outpatient");
    else comp.outpatient = b.hospital_cost * p.outpatient_multiplier;
  }
  if (p.use_deaths) {
    if (!isNum(b.deaths) || !isNum(b.productive_years_lost) || !isNum(b.daily_income)) missing.push("deaths");
    else comp.deaths = b.deaths * b.productive_years_lost * (b.daily_income * 365.0);
  }
  return { comp, missing };
}

export function presentValue(annual: number, horizon: number, rate: number, dropOff = 0, adjust = 1): number {
  let total = 0.0;
  let disc = 1.0;
  let keep = 1.0;
  const growth = 1.0 + rate;
  const retain = 1.0 - dropOff;
  for (let i = 0; i < horizon; i++) {
    disc = disc * growth;
    total = total + (annual * adjust * keep) / disc;
    keep = keep * retain;
  }
  return total;
}

export function calculate(b: Baseline, p: Params): Result {
  validate(p);
  const { comp, missing } = components(b, p);
  let base = 0.0;
  for (const k of ["hospital", "productivity", "outpatient", "deaths"]) if (k in comp) base = base + comp[k];
  const r = p.reduction_pct / 100.0;
  const annual = base * r;
  const pv = presentValue(annual, p.horizon_years, p.discount_rate);
  const school = isNum(b.school_days) ? b.school_days * r : null;
  const res: Result = { annual_base: base, components: comp, annual_saving: annual, pv_saving: pv,
    school_days_avoided: school, sroi_pv: null, sroi_ratio: null, missing };
  if (p.investment !== null && p.investment > 0) {
    const adjust = (1.0 - p.deadweight) * p.attribution;
    res.sroi_pv = presentValue(annual, p.horizon_years, p.discount_rate, p.drop_off, adjust);
    res.sroi_ratio = res.sroi_pv / p.investment;
  }
  return res;
}

export function sensitivity(b: Baseline, p: Params, ranges: Partial<Record<"discount_rate" | "deadweight" | "attribution" | "drop_off", [number, number]>>): [number, number] {
  const [loRate, hiRate] = ranges.discount_rate ?? [p.discount_rate, p.discount_rate];
  const sroi = p.investment !== null && p.investment > 0;
  if (!sroi) {
    return [calculate(b, { ...p, discount_rate: hiRate }).pv_saving, calculate(b, { ...p, discount_rate: loRate }).pv_saving];
  }
  const dw = ranges.deadweight ?? [p.deadweight, p.deadweight];
  const at = ranges.attribution ?? [p.attribution, p.attribution];
  const dr = ranges.drop_off ?? [p.drop_off, p.drop_off];
  const worst = calculate(b, { ...p, discount_rate: hiRate, deadweight: dw[1], attribution: at[0], drop_off: dr[1] });
  const best = calculate(b, { ...p, discount_rate: loRate, deadweight: dw[0], attribution: at[1], drop_off: dr[0] });
  return [worst.sroi_pv ?? 0, best.sroi_pv ?? 0];
}

/** Parâmetros ↔ URL (link compartilhável). */
export function toQuery(p: Params): string {
  const q = new URLSearchParams({ r: String(p.reduction_pct), h: String(p.horizon_years), t: String(p.discount_rate),
    hosp: p.use_hospital ? "1" : "0", prod: p.use_productivity ? "1" : "0" });
  if (p.investment) { q.set("inv", String(p.investment)); q.set("dw", String(p.deadweight)); q.set("at", String(p.attribution)); q.set("do", String(p.drop_off)); }
  return q.toString();
}

export function fromQuery(q: URLSearchParams, base: Params = DEFAULT_PARAMS): Params {
  const num = (k: string, d: number, lo: number, hi: number) => {
    const v = Number(q.get(k));
    return q.has(k) && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d;
  };
  const inv = q.has("inv") ? num("inv", 0, 0, 1e12) : null;
  return {
    ...base,
    reduction_pct: num("r", base.reduction_pct, 0, 100),
    horizon_years: Math.round(num("h", base.horizon_years, 1, 30)),
    discount_rate: num("t", base.discount_rate, 0, 0.3),
    use_hospital: q.get("hosp") !== "0",
    use_productivity: q.get("prod") !== "0",
    investment: inv && inv > 0 ? inv : null,
    deadweight: num("dw", base.deadweight, 0, 1),
    attribution: num("at", base.attribution, 0, 1),
    drop_off: num("do", base.drop_off, 0, 1),
  };
}
