import { describe, expect, it } from "vitest";
import { buildIndex, search } from "./search";

const docs = [
  { id: "1", type: "Município", title: "Feira de Santana", sub: "BA", url: "/a", text: "" },
  { id: "2", type: "Município", title: "São Gonçalo do Amarante", sub: "CE", url: "/b", text: "" },
  { id: "3", type: "Município", title: "Juazeiro", sub: "BA", url: "/c", text: "" },
  { id: "4", type: "Indicador", title: "Atendimento total de esgoto", sub: "", url: "/d", text: "" },
];
const ms = buildIndex(docs);

describe("busca de municípios", () => {
  it("ignora acentos", () => expect(search(ms, "sao goncalo")[0].id).toBe("2"));
  it("tolera erro de digitação", () => expect(search(ms, "juazero")[0].id).toBe("3"));
  it("busca por prefixo", () => expect(search(ms, "feir")[0].id).toBe("1"));
  it("acha indicadores por sinônimo", () => expect(search(ms, "saneamento")[0].id).toBe("4"));
});
