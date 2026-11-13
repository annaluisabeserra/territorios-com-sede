import type { APIRoute } from "astro";
import { ficha, resumo, ufs } from "../../../lib/data";
import { fmtNumber, fmtPct } from "../../../lib/format";
import { THERMO_LABEL } from "../../../lib/indicators";
import { card } from "../../../lib/og";

export function getStaticPaths() {
  return ufs().flatMap((u) => resumo(u.slug).municipios.map((m) => ({ params: { uf: u.slug, slug: m.slug } })));
}

export const GET: APIRoute = async ({ params }) => {
  const f = ficha(params.uf!, params.slug!);
  const h = f.health;
  const stats = [
    { v: fmtPct(f.ind.snis_agua_pct), l: `da população atendida com água (SNIS${f.ind_ano.snis_agua_pct ? ` ${f.ind_ano.snis_agua_pct}` : ""})` },
    f.ind.snis_esgoto_tratado_pct === null && f.esgoto_sem_declaracao
      ? { v: "sem rede", l: "nenhum prestador de esgoto declarado ao SNIS" }
      : { v: fmtPct(f.ind.snis_esgoto_tratado_pct), l: `com esgoto coletado e tratado (SNIS${f.ind_ano.snis_esgoto_tratado_pct ? ` ${f.ind_ano.snis_esgoto_tratado_pct}` : ""})` },
    h ? { v: fmtNumber(h.internacoes), l: "internações por ano por doenças ligadas à água" }
      : { v: THERMO_LABEL[f.thermometer.esgoto.status], l: "meta de esgoto de 2033" },
  ];
  const png = await card({ title: f.nome, subtitle: `${f.uf_nome} · ${fmtNumber(f.ind.populacao)} moradores`, stats, url: `territorios.institutosdw.org/municipio/${params.uf}/${params.slug}` });
  return new Response(new Uint8Array(png), { headers: { "Content-Type": "image/png" } });
};
