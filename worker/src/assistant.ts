/**
 * Assistente de dados (SPEC §6.15). Desligado por padrão (ASSISTANT_ENABLED=false).
 * Regra de ouro: responde só com base nos dados da plataforma, via ferramentas que leem os JSON publicados no
 * site, sempre citando fonte e data, e diz "não sei" quando o dado não existe.
 */
import Anthropic from "@anthropic-ai/sdk";

export interface AssistantEnv { ANTHROPIC_API_KEY?: string; ASSISTANT_MODEL?: string; SITE_ORIGIN: string }

const SYSTEM = `Você é o assistente do observatório Territórios com Sede (Instituto SDW). Responda em português do Brasil,
com frases curtas e linguagem simples.
Regras:
- Use SOMENTE informações devolvidas pelas ferramentas. Não use conhecimento próprio sobre números, leis ou municípios.
- Sempre cite a fonte e a data de referência que vierem no resultado da ferramenta.
- Se a ferramenta não trouxer o dado, ou trouxer "sem dado", diga claramente que não sabe ou que o dado não existe.
- Nunca transforme ausência de dado em zero. Estimativas devem ser apresentadas como estimativas.
- Não forneça localização de aldeias, casas ou comunidades; só informações agregadas por município.
- Se a pergunta não for sobre água, saneamento, saúde ou os dados da plataforma, diga que não pode ajudar com isso.`;

const TOOLS: Anthropic.Beta.BetaTool[] = [
  {
    name: "buscar_municipio",
    description: "Devolve a ficha de um município (indicadores com ano, termômetro 2033, comunidades, fontes). Use o nome do município e a sigla da UF.",
    input_schema: { type: "object", properties: { uf: { type: "string", description: "Sigla da UF, ex.: BA" }, nome: { type: "string" } }, required: ["uf", "nome"], additionalProperties: false },
    strict: true,
  },
  {
    name: "definicao_indicador",
    description: "Devolve fórmula, fonte e limitações de um indicador da plataforma, a partir de palavras-chave (ex.: 'esgoto tratado').",
    input_schema: { type: "object", properties: { termo: { type: "string" } }, required: ["termo"], additionalProperties: false },
    strict: true,
  },
  {
    name: "ranking",
    description: "Lista os municípios de uma UF ordenados por um indicador (id exato, ex.: snis_agua_pct). Ordem 'asc' ou 'desc'.",
    input_schema: { type: "object", properties: { uf: { type: "string" }, indicador: { type: "string" }, ordem: { type: "string", enum: ["asc", "desc"] }, n: { type: "integer" } }, required: ["uf", "indicador", "ordem", "n"], additionalProperties: false },
    strict: true,
  },
];

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

async function getJson(env: AssistantEnv, path: string): Promise<any | null> {
  const r = await fetch(`${env.SITE_ORIGIN}/data/${path}`, { cf: { cacheTtl: 3600 } } as RequestInit);
  return r.ok ? r.json() : null;
}

async function runTool(env: AssistantEnv, name: string, input: any): Promise<string> {
  const uf = String(input.uf ?? "").toLowerCase().slice(0, 2);
  if (name === "buscar_municipio") {
    const resumo = await getJson(env, `${uf}/resumo.json`);
    const m = resumo?.municipios.find((x: any) => norm(x.nome) === norm(String(input.nome)));
    if (!m) return JSON.stringify({ erro: "município não encontrado nos dados da plataforma" });
    const f = await getJson(env, `${uf}/municipios/${m.slug}.json`);
    const fontes = Object.fromEntries(Object.entries(resumo.sources).map(([k, s]: any) => [k, { nome: s.name, status: s.status, periodo: s.reference_period }]));
    return JSON.stringify({ municipio: f.nome, uf: f.uf, resumo: f.resumo, indicadores: f.ind, ano_dos_indicadores: f.ind_ano,
      termometro_2033: { agua: f.thermometer.agua.status, esgoto_coletado_tratado: f.thermometer.esgoto.status },
      comunidades: f.communities, fontes, gerado_em: f.generated_at, link: `${env.SITE_ORIGIN}/municipio/${uf}/${m.slug}` });
  }
  if (name === "definicao_indicador") {
    const ind = await getJson(env, "indicadores.json");
    const t = norm(String(input.termo));
    const hits = Object.entries(ind ?? {}).filter(([k, d]: any) => norm(`${k} ${d.label}`).includes(t)).slice(0, 3);
    return hits.length ? JSON.stringify(Object.fromEntries(hits)) : JSON.stringify({ erro: "indicador não encontrado" });
  }
  if (name === "ranking") {
    const resumo = await getJson(env, `${uf}/resumo.json`);
    if (!resumo) return JSON.stringify({ erro: "UF não disponível" });
    const n = Math.min(20, Math.max(1, Number(input.n) || 10));
    const rows = resumo.municipios.filter((m: any) => m.ind[input.indicador] != null)
      .sort((a: any, b: any) => (input.ordem === "asc" ? 1 : -1) * (a.ind[input.indicador] - b.ind[input.indicador])).slice(0, n)
      .map((m: any) => ({ municipio: m.nome, valor: m.ind[input.indicador] }));
    const sem = resumo.municipios.filter((m: any) => m.ind[input.indicador] == null).length;
    return JSON.stringify({ indicador: input.indicador, uf: resumo.uf.sigla, municipios: rows, municipios_sem_dado: sem, gerado_em: resumo.generated_at });
  }
  return JSON.stringify({ erro: "ferramenta desconhecida" });
}

export async function answer(env: AssistantEnv, question: string): Promise<{ text: string; refused?: boolean }> {
  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  const messages: Anthropic.Beta.BetaMessageParam[] = [{ role: "user", content: question.slice(0, 1000) }];
  for (let i = 0; i < 6; i++) {
    const response = await client.beta.messages.create({
      model: env.ASSISTANT_MODEL || "claude-opus-5-5",
      max_tokens: 16000,
      system: SYSTEM,
      tools: TOOLS,
      output_config: { effort: "low" },
      // Fallback em caso de recusa por classificador de segurança: a API reexecuta no modelo de reserva.
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      messages,
    });
    if (response.stop_reason === "refusal") return { text: "Não posso responder a essa pergunta.", refused: true };
    if (response.stop_reason === "pause_turn") { messages.push({ role: "assistant", content: response.content }); continue; }
    if (response.stop_reason !== "tool_use") {
      const text = response.content.filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text").map((b) => b.text).join("\n");
      return { text: text || "Não sei responder com os dados da plataforma." };
    }
    messages.push({ role: "assistant", content: response.content });
    const results: Anthropic.Beta.BetaToolResultBlockParam[] = [];
    for (const b of response.content) {
      if (b.type !== "tool_use") continue;
      try {
        results.push({ type: "tool_result", tool_use_id: b.id, content: await runTool(env, b.name, b.input) });
      } catch (e) {
        results.push({ type: "tool_result", tool_use_id: b.id, content: `erro: ${(e as Error).message}`, is_error: true });
      }
    }
    messages.push({ role: "user", content: results });
  }
  return { text: "Não consegui concluir a consulta. Tente uma pergunta mais simples." };
}
