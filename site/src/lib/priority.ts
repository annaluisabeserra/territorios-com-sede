/**
 * Índice de prioridade com pesos ajustáveis (SPEC §6.6). Espelho exato de weighted_index em
 * pipeline/transform/priority_index.py, testado contra priority.parity.json.
 */
export function weightedIndex(
  dimScores: Record<string, number | null>,
  weights: Record<string, number>,
  minDims: number,
  required: string[] = [],
): [number | null, number] {
  const present = Object.entries(dimScores).filter(([d, s]) => s !== null && !Number.isNaN(s) && (weights[d] ?? 0) > 0) as [string, number][];
  let totalW = 0.0;
  for (const [d] of present) totalW = totalW + weights[d];
  let allW = 0.0;
  for (const d of Object.keys(dimScores)) allW = allW + (weights[d] ?? 0.0);
  const coverage = allW > 0 ? totalW / allW : 0.0;
  const names = new Set(present.map(([d]) => d));
  if (present.length < minDims || totalW <= 0 || required.some((r) => !names.has(r))) return [null, coverage];
  let acc = 0.0;
  for (const [d, s] of present) acc = acc + s * weights[d];
  return [acc / totalW, coverage];
}

/** Posição 1 = maior prioridade; empates com a mesma posição; desempate de ordem pelo código. */
export function rank(scores: Record<string, number | null>): Record<string, number | null> {
  const present = Object.entries(scores).filter(([, v]) => v !== null) as [string, number][];
  present.sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  const out: Record<string, number | null> = Object.fromEntries(Object.keys(scores).map((k) => [k, null]));
  let prev: number | null = null, pos = 0;
  present.forEach(([k, v], i) => { if (v !== prev) { pos = i + 1; prev = v; } out[k] = pos; });
  return out;
}
