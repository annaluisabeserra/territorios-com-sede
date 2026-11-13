// Copia data/public → site/public/data e gera a malha web simplificada (mapshaper).
// Rodado antes do dev e do build (`npm run sync`). Falha alto se não houver dados processados.
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import mapshaper from "mapshaper";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../data/public");
const dst = resolve(here, "../public/data");

if (!existsSync(join(src, "index.json"))) {
  console.error("data/public/index.json não encontrado. Rode antes: uv run python -m pipeline.run --only-build");
  process.exit(1);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
cpSync(src, dst, { recursive: true, filter: (p) => !p.endsWith("malha.geojson") });

const index = JSON.parse(readFileSync(join(src, "index.json"), "utf8"));
for (const uf of index.ufs) {
  const input = join(src, uf.slug, "malha.geojson");
  const output = join(dst, uf.slug, "mapa.geojson");
  // Simplificação com topologia preservada (sem buracos entre vizinhos), 5 casas decimais (~1 m).
  await mapshaper.runCommands(
    `-i "${input}" -simplify 5% keep-shapes -clean -o "${output}" precision=0.0001 format=geojson`,
  );
  const kb = (statSync(output).size / 1024).toFixed(0);
  console.log(`[${uf.sigla}] mapa.geojson: ${kb} KB`);
  // Versão bem leve e projetada para o mapa estático em SVG (home e fichas, sem JavaScript)
  await mapshaper.runCommands(
    `-i "${input}" -simplify 1.2% keep-shapes -clean -proj EPSG:5880 -o "${join(dst, uf.slug, "mapa-svg.geojson")}" format=geojson precision=100`,
  );
}
writeFileSync(join(dst, ".synced"), new Date().toISOString());
console.log("dados sincronizados em", dst);
