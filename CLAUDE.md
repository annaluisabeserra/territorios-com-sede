# CLAUDE.md — Territórios com Sede

Observatório de água e saneamento do Instituto SDW. Fonte da verdade: `docs/SPEC.md`.
Frase-missão: *"Que ninguém adoeça por causa da água que bebe."*

## Regras inegociáveis (resumo da SPEC §2 e §7)

- **Custo zero**: só software livre e planos gratuitos, cada um com plano de saída (`HANDOFF.md`).
- **Site estático**; dados processados em lote (GitHub Actions) e servidos como arquivos.
- **Zero número inventado**: todo valor exibido tem fonte, data de referência e fórmula.
  Indisponível = `null` no JSON = "sem dado" na interface. Nunca zero.
- Estimativas rotuladas como estimativas, com premissas visíveis.
- **Povos e comunidades tradicionais**: só polígonos oficiais públicos e contagens agregadas por município.
  Nunca ponto exato. Status oficial com fonte.
- **LGPD**: nenhum dado pessoal, nenhum cookie, eventos anônimos e agregados.
- **WCAG 2.1 AA**, mobile-first, ficha < 200 KB de JS, Lighthouse ≥ 90.
- Interface e docs em **pt-BR** com linguagem simples; código e identificadores em inglês.
- **Parametrizado por UF**: outro estado = mudar `pipeline/config/ufs.yaml`, nunca o código.

## Modo de trabalho

- Marcos M0–M8 (SPEC §10). Ciclo: planejar → implementar → testar → validar dados →
  revisão crítica (SPEC §11, `docs/REVIEWS/M<n>.md`) → corrigir → `docs/PROGRESS.md` → commit.
- Dúvida: decisão conservadora + ADR em `docs/DECISIONS.md`. Dúvida humana: `docs/QUESTIONS.md`.
- Commits pequenos, Conventional Commits em português (`feat:`, `fix:`, `data:`, `docs:`, `test:`).
- Fontes externas citadas na SPEC são pontos de partida: verificar e registrar em `docs/DATA_SOURCES.md`.

## Estrutura

```
pipeline/            Python (uv): ingestão, transformação, validação
  sources/           um módulo por fonte (download + parse + metadados)
  transform/         indicadores, calculadora, termômetro, índice
  validate/          schemas Pandera e checagens de sanidade
  config/            ufs.yaml, indicadores.yaml, cid_drsai.yaml, pesos_indice.yaml, calculadora.yaml
  tests/             pytest (+ fixtures sintéticas só para teste, nunca publicadas)
data/raw/            cache de downloads (gitignored)
data/processed/      Parquet por UF
data/public/         JSON e downloads consumidos pelo site
site/                Astro (estático) + ilhas TS
worker/              Cloudflare Worker de aprendizado (opcional, desligado por padrão)
docs/                SPEC, METODOLOGIA, DATA_SOURCES, DECISIONS, PROGRESS, QUESTIONS, REVIEWS
.github/workflows/   ci, data-refresh, deploy, learning-report
```

## Comandos

```bash
make setup      # instala deps Python (uv) e Node (npm)
make lint       # ruff + tsc/astro check
make test       # pytest + vitest
make data UF=BA # roda o pipeline para uma UF (todas as ativas se omitido)
make dev        # site em modo desenvolvimento
make build      # build estático completo
make e2e        # Playwright + axe
```

## Convenções de dados

- Chave universal: código IBGE de 7 dígitos (`cod_ibge7`, string). DATASUS usa 6 (`cod_ibge6`):
  converter só via tabela de-para validada (`pipeline/transform/geo_keys.py`).
- Todo arquivo de saída tem um `.meta.json` irmão: fonte, URL, coleta, período, versão do pipeline.
- Valores monetários em R$ reais constantes do ano indicado em `meta.price_base` (IPCA).
- Percentuais em escala 0–100.
