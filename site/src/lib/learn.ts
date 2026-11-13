/**
 * Aprendizado com o uso (SPEC §6.14). Envia eventos anônimos ao Worker SOMENTE se PUBLIC_LEARNING_ENDPOINT
 * estiver definido no build. Sem cookies, sem identificador, sem IP armazenado (o Worker descarta).
 * O site funciona 100% sem isto.
 */
const endpoint = import.meta.env.PUBLIC_LEARNING_ENDPOINT as string | undefined;

export type LearnEvent = "search_no_result" | "guided_question" | "calc_scenario";

export function track(type: LearnEvent, data: Record<string, string | number>): void {
  if (!endpoint || typeof navigator === "undefined") return;
  try {
    const body = JSON.stringify({ type, data, path: location.pathname });
    // text/plain: tipo "simples", sem preflight de CORS (o Worker lê o corpo como texto e faz o parse)
    if (!navigator.sendBeacon?.(endpoint, new Blob([body], { type: "text/plain" }))) {
      fetch(endpoint, { method: "POST", body, keepalive: true, headers: { "Content-Type": "text/plain" } });
    }
  } catch {
    /* aprendizado é opcional: nunca quebrar a página */
  }
}
