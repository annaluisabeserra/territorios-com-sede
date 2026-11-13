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

## ADR-003. Tabelas do Censo 2022 descobertas pelo catálogo do SIDRA

- **Contexto:** fontes secundárias citam números de tabela diferentes para o mesmo recorte do Censo 2022 (6803, 6804, 6909 para água). Não foi possível consultar o SIDRA do ambiente de construção.
- **Decisão:** o pipeline percorre o catálogo oficial (`/api/v3/agregados`), filtra os agregados do Censo Demográfico pelo nome, confere nos metadados período 2022, nível município (N6), variável de moradores e a classificação esperada, e escolhe a tabela mais simples. A tabela usada fica no `.meta.json`.
- **Alternativas:** fixar números de tabela (frágil, sem verificação); raspar o site do SIDRA.
- **Consequências:** robusto a erro de número; se o IBGE renomear agregados, a fonte fica indisponível com motivo explícito, em vez de trazer dado errado.

## ADR-004. Mapa municipal em GeoJSON simplificado e mapa base opcional

- **Contexto:** a SPEC sugere PMTiles com tippecanoe. Para 417 polígonos municipais, um GeoJSON simplificado (topologia preservada, coordenadas com 4 casas) fica em ~150–300 KB comprimido. O tippecanoe não está disponível no ambiente e o mapa base gratuito (OpenFreeMap) foi bloqueado aqui.
- **Decisão:** camada municipal em GeoJSON simplificado com mapshaper (npm), carregada sob demanda; mapa base vetorial do OpenFreeMap **opcional** (desligado por padrão para economizar dados em 3G). PMTiles fica reservado para camadas nacionais pesadas na Fase 1.
- **Alternativas:** PMTiles para tudo (mais ferramentas, nenhum ganho real em 417 polígonos); raster tiles de terceiros (dependência externa).
- **Consequências:** mapa funciona sem nenhum serviço externo; troca para PMTiles é localizada no componente do mapa.

## ADR-005. SIH: contagem por residência e regras de contagem

- **Contexto:** os arquivos RD do SIH são organizados pela UF do hospital. Moradores internados em outra UF só aparecem nos arquivos daquela UF.
- **Decisão:** ler as 27 UFs (`residence_scope: all_ufs`) e filtrar `MUNIC_RES` da UF. Internação = AIH com `IDENT ≠ 5`; valor = `VAL_TOT` de todas as AIHs; ano = ano de processamento (`ANO_CMPT`), como no padrão do TabNet. Cada arquivo vira um extrato DRSAI pequeno, mantido em cache (`actions/cache`), e o `.dbc` é apagado.
- **Alternativas:** ler só a própria UF (subconta moradores internados fora); ano de internação (`DT_INTER`), que exige reprocessar anos anteriores a cada mês.
- **Consequências:** primeira execução pesada (~1.600 arquivos para 5 anos); as seguintes só baixam meses novos. Conferência com o TabNet no `VALIDATION_REPORT.md`.

## ADR-006. Espelho com sigilo de células: rotular como mínimo

- **Contexto:** a população quilombola por município no espelho é a soma de células idade × sexo, e células pequenas vêm vazias por sigilo.
- **Decisão:** exibir como "pelo menos N pessoas" (flag `lower_bound`) até a tabela oficial de total (SIDRA) ser lida no GitHub Actions.
- **Consequências:** nenhum número apresentado como exato quando não é.

## ADR-007. Versionar `data/processed`, gerar `data/public` no deploy

- **Contexto:** os arquivos públicos (fichas JSON, CSVs por município, GeoJSON) somam ~9,5 MB por UF e chegariam a ~250 MB com 27 estados. Os Parquet processados somam ~1,6 MB por UF.
- **Decisão:** `data/processed/{uf}` é versionado (histórico por data no git); `data/public` é regenerado em segundos por `python -m pipeline.run --only-build` no workflow de deploy, antes do build do site.
- **Consequências:** repositório pequeno; o deploy depende de Python (já usado no CI). Os downloads abertos continuam publicados no site.
