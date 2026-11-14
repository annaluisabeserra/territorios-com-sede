import { describe, expect, it } from "vitest";
import { fmtDate, fmtBRL, fmtPct, fmtNumber, oneInN, fmtBRLShort, NO_DATA } from "./format";

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

describe("fmtDate", () => {
  it("formata em pt-BR e trata ausência", () => {
    expect(fmtDate("2026-03-05T15:00:00Z")).toBe("05/03/2026");
    expect(fmtDate(null)).toBe("sem dado");
    expect(fmtDate("lixo")).toBe("sem dado");
  });
});

describe("deUF/emUF", () => {
  it("usa a preposição do estado", async () => {
    const { deUF, emUF } = await import("./format");
    expect(deUF("Bahia", "da")).toBe("da Bahia");
    expect(emUF("Ceará", "do")).toBe("no Ceará");
    expect(emUF("Pernambuco", "de")).toBe("em Pernambuco");
    expect(deUF("Sergipe")).toBe("de Sergipe");
  });
});
