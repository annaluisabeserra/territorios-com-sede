// SVG base da UF (todos os municípios em tom neutro), compartilhado e cacheado entre as fichas.
import type { APIRoute } from "astro";
import { ufs } from "../../lib/data";
import { shapes } from "../../lib/svgmap";

export function getStaticPaths() {
  return ufs().map((u) => ({ params: { uf: u.slug } }));
}

export const GET: APIRoute = ({ params }) => {
  const { paths, viewBox } = shapes(params.uf as string);
  const body = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}"><g fill="#dbe9ee" stroke="#fff" stroke-width="0.6" stroke-linejoin="round">${paths.map((p) => `<path d="${p.d}"/>`).join("")}</g></svg>`;
  return new Response(body, { headers: { "Content-Type": "image/svg+xml" } });
};
