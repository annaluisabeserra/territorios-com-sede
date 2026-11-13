import MiniSearch from "minisearch";

export interface Doc { id: string; type: string; title: string; sub: string; url: string; text: string }

// Sinônimos simples (o relatório mensal de aprendizado sugere novos; uma pessoa aprova antes de entrar aqui).
const SYNONYMS: Record<string, string> = { saneamento: "esgoto", agua: "água", "esgoto tratado": "tratamento", diarreia: "drsai", doencas: "drsai" };

export const normalize = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function buildIndex(docs: Doc[]): MiniSearch<Doc> {
  const ms = new MiniSearch<Doc>({
    fields: ["title", "text", "sub"],
    storeFields: ["type", "title", "sub", "url"],
    processTerm: (t) => normalize(t),
    searchOptions: { boost: { title: 4, sub: 1 }, prefix: true, fuzzy: 0.25, combineWith: "AND" },
  });
  ms.addAll(docs);
  return ms;
}

export function search(ms: MiniSearch<Doc>, q: string) {
  const query = SYNONYMS[normalize(q.trim())] ?? q;
  let r = ms.search(query);
  if (r.length === 0) r = ms.search(query, { combineWith: "OR" });
  return r;
}
