// Converte a malha projetada (EPSG:5880, metros) em caminhos SVG, em tempo de build.
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

interface Feature { properties: { cod_ibge7: string; nome: string; slug: string }; geometry: { type: string; coordinates: any } }
export interface ShapePath { cod: string; nome: string; slug: string; d: string }

const cache = new Map<string, { paths: ShapePath[]; viewBox: string }>();

export function shapes(ufSlug: string): { paths: ShapePath[]; viewBox: string } {
  if (cache.has(ufSlug)) return cache.get(ufSlug)!;
  const gj = JSON.parse(readFileSync(join(resolve(process.cwd(), "public/data"), ufSlug, "mapa-svg.geojson"), "utf8"));
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const each = (rings: number[][][], f: (x: number, y: number) => void) => rings.forEach((r) => r.forEach(([x, y]) => f(x, y)));
  const polys = (g: Feature["geometry"]): number[][][][] => (g.type === "Polygon" ? [g.coordinates] : g.coordinates);
  for (const ft of gj.features as Feature[]) for (const p of polys(ft.geometry)) each(p, (x, y) => {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  });
  const scale = 1000 / Math.max(maxX - minX, maxY - minY);
  const tx = (x: number) => Math.round((x - minX) * scale * 10) / 10;
  const ty = (y: number) => Math.round((maxY - y) * scale * 10) / 10;
  const paths = (gj.features as Feature[]).map((ft) => {
    const d = polys(ft.geometry).map((poly) => poly.map((ring) =>
      "M" + ring.map(([x, y]) => `${tx(x)} ${ty(y)}`).join("L") + "Z").join("")).join("");
    return { cod: String(ft.properties.cod_ibge7), nome: ft.properties.nome, slug: ft.properties.slug, d };
  });
  const out = { paths, viewBox: `0 0 ${Math.ceil((maxX - minX) * scale)} ${Math.ceil((maxY - minY) * scale)}` };
  cache.set(ufSlug, out);
  return out;
}
