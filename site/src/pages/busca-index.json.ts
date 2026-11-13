// Índice de busca gerado no build: municípios (todas as UFs), indicadores, FAQ e páginas.
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { indicators, readJson, resumo, ufs } from "../lib/data";

const PAGES = [
  { t: "Mapa interativo", u: "/mapa", k: "mapa camadas esgoto água coberturas" },
  { t: "Calculadora de economia", u: "/calculadora", k: "custo economia sroi internações sus" },
  { t: "Perguntas guiadas e rankings", u: "/perguntas", k: "ranking comparação lista perguntas" },
  { t: "Índice de prioridade", u: "/indice", k: "prioridade onde investir pesos" },
  { t: "Metodologia", u: "/metodologia", k: "fórmula fonte cálculo como" },
  { t: "Dados abertos", u: "/dados", k: "download csv parquet dicionário licença" },
  { t: "Escola", u: "/escola", k: "professor aluno atividade sala de aula" },
  { t: "Povos e comunidades tradicionais", u: "/povos-e-comunidades", k: "quilombola indígena terra território retirada" },
  { t: "Sobre", u: "/sobre", k: "instituto sdw contato corrigir" },
];

export const GET: APIRoute = async () => {
  const docs: { id: string; type: string; title: string; sub: string; url: string; text: string }[] = [];
  for (const u of ufs()) {
    for (const m of resumo(u.slug).municipios) {
      docs.push({ id: `m-${m.cod}`, type: "Município", title: m.nome, sub: `${u.sigla} · ${m.ri ?? ""}`, url: `/municipio/${u.slug}/${m.slug}`, text: `${m.rim ?? ""} ${m.ri ?? ""}` });
    }
  }
  // Terras indígenas e reservas extrativistas: nome do território (nível de território, nunca aldeia)
  for (const u of ufs()) {
    for (const [file, label] of [["terras_indigenas.geojson", "Terra indígena"], ["ucs_uso_sustentavel.geojson", "Reserva"]] as const) {
      const gj = readJson<any>(u.slug, file);
      (gj?.features ?? []).forEach((ft: any, i: number) => {
        const p = ft.properties ?? {};
        docs.push({ id: `t-${u.slug}-${label}-${i}`, type: label, title: p.nome, sub: `${u.sigla} · ${p.fase ?? p.categoria ?? ""}`, url: `/mapa?uf=${u.slug}`, text: p.etnia ?? "" });
      });
    }
  }
  for (const [k, d] of Object.entries(indicators())) {
    docs.push({ id: `i-${k}`, type: "Indicador", title: d.label, sub: "Metodologia", url: `/metodologia#ind-${k}`, text: d.formula });
  }
  for (const f of await getCollection("faq")) {
    docs.push({ id: `f-${f.id}`, type: "Pergunta", title: f.data.question, sub: f.data.category, url: `/faq#${f.id}`, text: f.body ?? "" });
  }
  PAGES.forEach((p, i) => docs.push({ id: `p-${i}`, type: "Página", title: p.t, sub: "", url: p.u, text: p.k }));
  return new Response(JSON.stringify(docs), { headers: { "Content-Type": "application/json" } });
};
