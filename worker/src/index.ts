/**
 * Worker opcional (SPEC §6.14 e §6.15).
 *   POST /event      evento anônimo de uso → contador mensal no D1 (sem IP, cookie ou identificador)
 *   GET  /report     agregados do mês anterior (Bearer REPORT_TOKEN), lido pelo workflow learning-report
 *   POST /assistant  assistente de dados, só se ASSISTANT_ENABLED = "true"
 */
import { answer } from "./assistant";
import { cleanKey, month } from "./privacy";

export interface Env {
  DB: D1Database;
  SITE_ORIGIN: string;
  REPORT_TOKEN?: string;
  ASSISTANT_ENABLED?: string;
  ASSISTANT_MODEL?: string;
  ANTHROPIC_API_KEY?: string;
}

const cors = (env: Env) => ({
  "Access-Control-Allow-Origin": env.SITE_ORIGIN,
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
});

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(env) });

    if (url.pathname === "/event" && req.method === "POST") {
      const body = await req.text();
      if (body.length > 2000) return new Response(null, { status: 413, headers: cors(env) });
      let ev: { type?: string; data?: unknown };
      try { ev = JSON.parse(body); } catch { return new Response(null, { status: 400, headers: cors(env) }); }
      const key = cleanKey(String(ev.type), ev.data);
      if (key) {
        await env.DB.prepare(
          "INSERT INTO eventos (mes, tipo, chave, total) VALUES (?1, ?2, ?3, 1) ON CONFLICT(mes, tipo, chave) DO UPDATE SET total = total + 1",
        ).bind(month(), ev.type, key).run();
      }
      return new Response(null, { status: 204, headers: cors(env) });
    }

    if (url.pathname === "/report" && req.method === "GET") {
      if (!env.REPORT_TOKEN || req.headers.get("Authorization") !== `Bearer ${env.REPORT_TOKEN}`) return new Response("não autorizado", { status: 401 });
      const d = new Date(); d.setUTCMonth(d.getUTCMonth() - 1);
      const mes = url.searchParams.get("mes") ?? month(d);
      const { results } = await env.DB.prepare("SELECT tipo, chave, total FROM eventos WHERE mes = ?1 ORDER BY total DESC LIMIT 300").bind(mes).all();
      return Response.json({ mes, eventos: results });
    }

    if (url.pathname === "/assistant" && req.method === "POST") {
      if (env.ASSISTANT_ENABLED !== "true" || !env.ANTHROPIC_API_KEY) return Response.json({ enabled: false }, { status: 503, headers: cors(env) });
      const { pergunta } = (await req.json().catch(() => ({}))) as { pergunta?: string };
      if (!pergunta || pergunta.length < 3) return Response.json({ erro: "pergunta vazia" }, { status: 400, headers: cors(env) });
      try {
        return Response.json(await answer(env, pergunta), { headers: cors(env) });
      } catch {
        return Response.json({ text: "O assistente está indisponível agora. Tente mais tarde." }, { status: 502, headers: cors(env) });
      }
    }
    return new Response("Territórios com Sede: worker de aprendizado", { status: 404 });
  },
};
