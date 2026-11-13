-- Só contadores agregados por mês. Nenhum IP, user-agent, cookie, identificador ou carimbo de hora individual.
CREATE TABLE IF NOT EXISTS eventos (
  mes   TEXT NOT NULL,           -- AAAA-MM
  tipo  TEXT NOT NULL,           -- search_no_result | guided_question | calc_scenario
  chave TEXT NOT NULL,           -- termo normalizado ou combinação de parâmetros (truncada)
  total INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (mes, tipo, chave)
);

-- Teto de uso do assistente: só contadores por dia e por minuto (nenhum dado de quem perguntou).
CREATE TABLE IF NOT EXISTS uso_assistente (
  janela TEXT PRIMARY KEY,       -- d:AAAA-MM-DD ou m:AAAA-MM-DDTHH:MM
  total  INTEGER NOT NULL DEFAULT 0
);
