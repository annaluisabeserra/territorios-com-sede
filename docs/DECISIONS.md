# Decisões (ADR curtas)

Formato: contexto → decisão → alternativas → consequências.

## ADR-001. Versão do Python

- **Contexto:** a SPEC recomenda Python 3.12; o ambiente de construção tem 3.13.
- **Decisão:** `requires-python = ">=3.12"`. CI roda em 3.12 (a versão da SPEC); o código não usa recursos exclusivos da 3.13.
- **Alternativas:** fixar 3.12 com `uv python install` (depende de download do GitHub).
- **Consequências:** compatível com as duas versões; o CI garante 3.12.

## ADR-002. Ambiente de construção sem acesso às fontes oficiais

- **Contexto:** a política de rede do ambiente onde a plataforma foi construída bloqueia os domínios do governo (IBGE, DATASUS, gov.br, dados.gov.br, BCB). GitHub, PyPI e npm estão liberados.
- **Decisão:** (1) cada módulo de `pipeline/sources/` é escrito contra a URL oficial e roda no GitHub Actions, que tem rede aberta; (2) cada fonte aceita uma lista ordenada de URLs (`official` primeiro, depois `mirror`), e o `.meta.json` registra qual URL foi usada de fato; (3) espelhos só são aceitos quando redistribuem o arquivo oficial sem transformação de valores, ou quando a transformação é documentada e reprodutível; (4) o que não puder ser obtido fica `indisponível` com motivo, nunca simulado.
- **Alternativas:** fixtures sintéticas na interface (viola "zero número inventado"); esperar acesso de rede (bloquearia a entrega).
- **Consequências:** a primeira execução no GitHub Actions pode atualizar valores obtidos de espelhos. O `VALIDATION_REPORT.md` indica a origem de cada base. Pergunta Q1 registrada.
