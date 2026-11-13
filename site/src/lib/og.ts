// Card de compartilhamento 1200×630 (SPEC §6.11), gerado no build com Satori (SVG) + resvg (PNG).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

const font = (f: string) => readFileSync(resolve(process.cwd(), "node_modules/@fontsource/atkinson-hyperlegible/files", f));
const FONTS = [
  { name: "Atkinson", data: font("atkinson-hyperlegible-latin-400-normal.woff"), weight: 400 as const, style: "normal" as const },
  { name: "Atkinson", data: font("atkinson-hyperlegible-latin-700-normal.woff"), weight: 700 as const, style: "normal" as const },
];

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, style: Record<string, unknown>, children?: unknown): Node => ({ type, props: { style, children } });

export async function card(o: { title: string; subtitle: string; stats: { v: string; l: string }[]; url: string }): Promise<Buffer> {
  const inner = h("div", { width: 1072, height: 534, display: "flex", flexDirection: "column", justifyContent: "space-between" }, [
    h("div", { display: "flex", flexDirection: "column" }, [
      h("div", { fontSize: 30, color: "#7cc3d4", fontWeight: 700 }, "Seu território tem sede?"),
      h("div", { fontSize: o.title.length > 22 ? 72 : 88, fontWeight: 700, lineHeight: 1.05, marginTop: 12 }, o.title),
      h("div", { fontSize: 30, color: "#cfe6ee", marginTop: 8 }, o.subtitle),
    ]),
    h("div", { display: "flex", gap: 24, width: "100%" }, o.stats.map((s) =>
      h("div", { display: "flex", flexDirection: "column", flexGrow: 1, flexBasis: 0, minWidth: 0, background: "#0a3a52", borderRadius: 20, padding: "22px 26px" }, [
        h("div", { fontSize: s.v.length > 10 ? 40 : 52, fontWeight: 700 }, s.v),
        h("div", { fontSize: 24, color: "#cfe6ee", marginTop: 6, lineHeight: 1.25 }, s.l),
      ]))),
    h("div", { display: "flex", justifyContent: "space-between", fontSize: 22, color: "#9fcfdd", width: "100%" }, [
      h("div", {}, "Territórios com Sede · Instituto SDW"),
      h("div", {}, o.url),
    ]),
  ]);
  const tree = h("div", { width: 1200, height: 630, display: "flex", alignItems: "center", justifyContent: "center", background: "#062a3b", color: "#ffffff", fontFamily: "Atkinson" }, [inner]);
  const svg = await satori(tree as any, { width: 1200, height: 630, fonts: FONTS });
  return new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
}
