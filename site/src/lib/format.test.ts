import { describe, expect, it } from "vitest";
import { fmtBRL, fmtPct, fmtNumber, oneInN, fmtBRLShort, NO_DATA } from "./format";

describe("formatação pt-BR", () => {
  it("formata moeda e percentual no padrão brasileiro", () => {
    expect(fmtBRL(1234.56, 2)).toBe("R$ 1.234,56");
    expect(fmtPct(12.5)).toBe("12,5%");
    expect(fmtNumber(417)).toBe("417");
  });
  it("nunca transforma ausência em zero", () => {
    expect(fmtBRL(null)).toBe(NO_DATA);
    expect(fmtPct(undefined)).toBe(NO_DATA);
    expect(fmtNumber(Number.NaN)).toBe(NO_DATA);
  });
  it("abrevia valores grandes e gera frações legíveis", () => {
    expect(fmtBRLShort(12_345_678)).toBe("R$ 12,3 milhões");
    expect(oneInN(33.3)).toBe("1 em cada 3");
    expect(oneInN(1)).toBeNull();
  });
});
