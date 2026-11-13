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
  if (!Number.isInteger(p.horizon_years) || !(p.horizon_years >= 1 && p.horizon_years <= 30)) throw new RangeError("horizon_years deve ser inteiro entre 1 e 30");
  if (p.outpatient_multiplier < 0) throw new RangeError("outpatient_multiplier não pode ser negativo");
  if (p.investment !== null && p.investment < 0) throw new RangeError("investment não pode ser negativo");
  if (p.discount_rate < 0) throw new RangeError("discount_rate não pode ser negativa");
  for (const k of ["deadweight", "attribution", "drop_off"] as const) {
    if (!(p[k] >= 0 && p[k] <= 1)) throw new RangeError(`${k} deve estar entre 0 e 1`);
  }
}

const isNum = (v: number | null | undefined): v is number => v !== null && v !== undefined && !Number.isNaN(v);
const nonneg = (v: number | null | undefined): v is number => isNum(v) && v >= 0;

export function annuityFactor(years: number, rate: number): number {
  let total = 0.0;
  let disc = 1.0;
  const growth = 1.0 + rate;
  const n = Math.floor(years);
  for (let i = 0; i < n; i++) {
    disc = disc * growth;
    total = total + 1.0 / disc;
  }
  return total;
}

export function components(b: Baseline, p: Params): { comp: Record<string, number>; missing: string[] } {
  const comp: Record<string, number> = {};
  const missing: string[] = [];
  if (p.use_hospital) {
    if (!nonneg(b.hospital_cost)) missing.push("hospital");
    else comp.hospital = b.hospital_cost;
  }
  if (p.use_productivity) {
    if (!nonneg(b.hospital_days) || !nonneg(b.daily_income)) missing.push("productivity");
    else comp.productivity = b.hospital_days * b.daily_income;
  }
  if (p.use_outpatient) {
    if (!nonneg(b.hospital_cost) || p.outpatient_multiplier <= 0) missing.push("outpatient");
    else comp.outpatient = b.hospital_cost * p.outpatient_multiplier;
  }
  if (p.use_deaths) {
    if (!nonneg(b.deaths) || !nonneg(b.productive_years_lost) || !nonneg(b.daily_income)) missing.push("deaths");
    else {
      const annualIncome = b.daily_income * 365.0;
      comp.deaths = b.deaths * annuityFactor(b.productive_years_lost, p.discount_rate) * annualIncome;
    }
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
  const school = nonneg(b.school_days) ? b.school_days * r : null;
  const res: Result = { annual_base: base, components: comp, annual_saving: annual, pv_saving: pv,
    school_days_avoided: school, sroi_pv: null, sroi_ratio: null, missing };
  if (p.investment !== null && p.investment > 0) {
    const adjust = (1.0 - p.deadweight) * p.attribution;
    res.sroi_pv = presentValue(annual, p.horizon_years, p.discount_rate, p.drop_off, adjust);
    res.sroi_ratio = res.sroi_pv / p.investment;
  }
  return res;
}

export type Ranges = Partial<Record<"discount_rate" | "deadweight" | "attribution" | "drop_off", [number, number]>>;
export interface Sensitivity { pv: [number, number]; sroi_pv: [number, number] | null }

/** Intervalo que sempre contém o valor escolhido pelo usuário. */
function span(r: [number, number] | undefined, v: number): [number, number] {
  const [lo, hi] = r ?? [v, v];
  return [lo < v ? lo : v, hi > v ? hi : v];
}

export function sensitivity(b: Baseline, p: Params, ranges: Ranges): Sensitivity {
  const [loRate, hiRate] = span(ranges.discount_rate, p.discount_rate);
  const pv: [number, number] = [
    calculate(b, { ...p, discount_rate: hiRate }).pv_saving,
    calculate(b, { ...p, discount_rate: loRate }).pv_saving,
  ];
  if (!(p.investment !== null && p.investment > 0)) return { pv, sroi_pv: null };
  const dw = span(ranges.deadweight, p.deadweight);
  const at = span(ranges.attribution, p.attribution);
  const dr = span(ranges.drop_off, p.drop_off);
  const worst = calculate(b, { ...p, discount_rate: hiRate, deadweight: dw[1], attribution: at[0], drop_off: dr[1] });
  const best = calculate(b, { ...p, discount_rate: loRate, deadweight: dw[0], attribution: at[1], drop_off: dr[0] });
  return { pv, sroi_pv: [worst.sroi_pv ?? 0, best.sroi_pv ?? 0] };
}

/** Parâmetros ↔ URL (link compartilhável). */
export function toQuery(p: Params, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams({ r: String(p.reduction_pct), h: String(p.horizon_years), t: String(p.discount_rate),
    hosp: p.use_hospital ? "1" : "0", prod: p.use_productivity ? "1" : "0", ...extra });
  if (p.use_outpatient) { q.set("amb", "1"); q.set("ambm", String(p.outpatient_multiplier)); }
  if (p.use_deaths) q.set("obt", "1");
  if (p.investment) { q.set("inv", String(p.investment)); q.set("dw", String(p.deadweight)); q.set("at", String(p.attribution)); q.set("do", String(p.drop_off)); }
  return q.toString();
}

export function fromQuery(q: URLSearchParams, base: Params = DEFAULT_PARAMS): Params {
  const num = (k: string, d: number, lo: number, hi: number) => {
    const raw = q.get(k);
    if (raw === null || raw.trim() === "") return d; // vazio = ausente (não 0)
    const v = Number(raw);
    return Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d;
  };
  const inv = q.has("inv") ? num("inv", 0, 0, 1e12) : null;
  return {
    ...base,
    reduction_pct: num("r", base.reduction_pct, 0, 100),
    horizon_years: Math.round(num("h", base.horizon_years, 1, 30)),
    discount_rate: num("t", base.discount_rate, 0, 0.3),
    use_hospital: q.get("hosp") !== "0",
    use_productivity: q.get("prod") !== "0",
    use_outpatient: q.get("amb") === "1",
    outpatient_multiplier: num("ambm", base.outpatient_multiplier, 0, 100),
    use_deaths: q.get("obt") === "1",
    investment: inv && inv > 0 ? inv : null,
    deadweight: num("dw", base.deadweight, 0, 1),
    attribution: num("at", base.attribution, 0, 1),
    drop_off: num("do", base.drop_off, 0, 1),
  };
}
