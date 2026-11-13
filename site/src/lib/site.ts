// Endereços institucionais (um lugar só). Ajustar REPO_URL quando o repositório for publicado (ver HANDOFF).
export const REPO_URL = import.meta.env.PUBLIC_REPO_URL ?? "https://github.com/institutosdw/territorios-com-sede";
export const CONTACT_EMAIL = "contato@institutosdw.org";
export const ISSUE_URL = `${REPO_URL}/issues/new?template=correcao-de-dado.yml`;
export const REMOVAL_URL = `${REPO_URL}/issues/new?template=pedido-de-retirada.yml`;
