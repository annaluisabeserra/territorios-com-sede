import { describe, expect, it } from "vitest";
import parity from "./priority.parity.json";
import { rank, weightedIndex } from "./priority";

describe("paridade exata do índice Python × TypeScript", () => {
  for (const [i, c] of (parity.cases as any[]).entries()) {
    it(`caso ${i}`, () => {
      const [idx, cov] = weightedIndex(c.dims, c.weights, c.min_dims, c.required);
      expect(idx).toBe(c.index);
      expect(cov).toBe(c.coverage);
    });
  }
  it("ranking idêntico", () => expect(rank(parity.rank.scores as any)).toEqual(parity.rank.expected));
});
