/**
 * Camada de provedor do assistente (SPEC §6.15). Desligado por padrão: PUBLIC_ASSISTANT_ENABLED=false.
 * O navegador nunca guarda chave de API: o provedor real chama o Worker, que guarda o segredo e só responde
 * com base nas ferramentas que leem os dados da plataforma.
 */
export interface AssistantAnswer { text: string; refused?: boolean }

export interface AssistantProvider {
  readonly enabled: boolean;
  ask(question: string): Promise<AssistantAnswer>;
}

export class DisabledProvider implements AssistantProvider {
  readonly enabled = false;
  async ask(): Promise<AssistantAnswer> {
    return { text: "O assistente está desligado nesta versão da plataforma." };
  }
}

export class WorkerProvider implements AssistantProvider {
  readonly enabled = true;
  constructor(private endpoint: string) {}
  async ask(question: string): Promise<AssistantAnswer> {
    const r = await fetch(this.endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pergunta: question }) });
    if (r.status === 503) return { text: "O assistente está desligado no servidor." };
    if (!r.ok) return { text: "O assistente está indisponível agora. Tente mais tarde." };
    return r.json();
  }
}

export function getProvider(): AssistantProvider {
  const on = import.meta.env.PUBLIC_ASSISTANT_ENABLED === "true";
  const ep = import.meta.env.PUBLIC_LEARNING_ENDPOINT as string | undefined;
  return on && ep ? new WorkerProvider(ep.replace(/\/event$/, "/assistant")) : new DisabledProvider();
}
