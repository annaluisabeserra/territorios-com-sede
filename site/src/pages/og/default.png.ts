import type { APIRoute } from "astro";
import { card } from "../../lib/og";
export const GET: APIRoute = async () => {
  const png = await card({ title: "Territórios com Sede", subtitle: "Que ninguém adoeça por causa da água que bebe.", stats: [
    { v: "Ver", l: "a situação de cada município" }, { v: "Calcular", l: "o custo de não ter saneamento" }, { v: "Agir", l: "onde o investimento rende mais" }], url: "territorios.institutosdw.org" });
  return new Response(new Uint8Array(png), { headers: { "Content-Type": "image/png" } });
};
