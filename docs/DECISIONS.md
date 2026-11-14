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

## ADR-008. Frescor do SNIS, meta de esgoto e regras do termômetro (revisão M2)

- **Contexto:** a revisão crítica do M2 mostrou que (a) valores muito antigos do SNIS (até 2010) eram usados como atuais; (b) o termômetro de esgoto usava o IN056 (coleta), mas a meta da Lei 14.026/2020 exige coleta **e** tratamento; 26 dos 39 municípios "no ritmo" tinham tratamento 0%; (c) a projeção aceitava séries antigas, projetava para o passado e marcava "meta atingida" com um único ponto.
- **Decisão:** (1) valor do SNIS com mais de 2 anos antes do último ano da UF é "desatualizado": aparece com o ano, mas não entra no índice, no "Agir", nas medianas nem no resumo; (2) a meta de esgoto é medida por "esgoto coletado e tratado" = IN056 × IN016 ÷ 100; (3) termômetro com janela de 8 anos terminando no último ano do SNIS, último ponto obrigatório nos 2 anos mais recentes, "atingida" só com 2 anos consecutivos acima da meta, projeção a partir do valor observado e nunca para antes do ano seguinte ao de referência, marcação de "projeção incerta" quando o IC 95% da tendência inclui estagnação; (4) valores entre 100% e 105% são limitados a 100, e acima de 105% viram ausentes.
- **Alternativas:** IN046 (tratado ÷ água consumida) como proxy da meta; min(IN056, IN046).
- **Consequências:** na BA, 10 municípios no ritmo da meta de esgoto (antes 39), 237 sem dados suficientes. O número é menos animador e mais honesto.

## ADR-009. Extratos do SIH compactos e guardados num Release

- **Contexto:** o `actions/cache` expira em 7 dias, então numa execução mensal o cache estaria sempre frio. Além disso, extratos linha a linha (idade, CID, óbito) seriam microdados num artefato público.
- **Decisão:** cada arquivo RD vira um extrato **agregado** por município × mês × grupo DRSAI × faixa etária (0–4, 5, 6–13, 14–17, 18+, desconhecida), sem dados individuais. Os extratos são guardados num Release `sih-extracts` (gratuito e permanente) e restaurados a cada execução. Os últimos 12 meses são sempre reprocessados, porque o DATASUS republica competências.
- **Consequências:** a primeira carga é pesada (pode exigir execuções por UF via `workflow_dispatch`); as seguintes baixam só os meses recentes.

## ADR-010. Parâmetros padrão da calculadora

- **Taxa de desconto:** 8,5% real ao ano, taxa social de desconto recomendada para projetos de infraestrutura pela nota técnica do governo federal de 2020 (Catálogo de Parâmetros do Guia Geral de ACB). Sensibilidade: 4% a 12%.
- **Custo hospitalar:** valor total das AIHs (tabela SUS), corrigido mês a mês pelo IPCA para reais do ano-base; subestima o custo econômico real (escolha conservadora).
- **Produtividade:** dias de internação × renda diária de referência (rendimento domiciliar per capita do Censo ÷ 30). Usa a renda per capita, menor que a renda do trabalho, porque o paciente médio inclui crianças e idosos. Para menores de 14 anos o dia é do adulto acompanhante, com a mesma renda de referência. Enquanto a renda municipal do Censo 2022 não estiver integrada, o componente fica "sem dado".
- **SROI:** deadweight 10%, atribuição 80%, drop-off 5% ao ano, com faixas de sensibilidade (0–30%, 50–100%, 0–15%). Valores conservadores típicos de análises SROI de saneamento; revisão por especialista registrada em Q5.
- **Desligados por padrão:** atendimento ambulatorial (sem multiplicador com referência) e óbitos (SIM sem causa disponível; abordagem sensível).

## ADR-012. SINISA continua a série do SNIS, com quebra sinalizada

- **Contexto:** o SNIS termina no ano de referência 2022; o SINISA o substitui e publica planilhas por edição, com nomes de arquivo que mudam e códigos novos de indicador. O gov.br não é alcançável do ambiente de desenvolvimento, só do GitHub Actions.
- **Decisão:** leitor que descobre as planilhas na página de cada edição (`sources.yaml → sinisa.pages`) e reconhece colunas por código (IAG0001, IES0001, IES2003, equivalências publicadas por Trata Brasil/GO Associados e ABES em 2025) ou por padrão de cabeçalho configurável. Os anos do SINISA só entram depois do último ano do SNIS. Tendências que atravessam a troca de sistema ficam marcadas como incertas, em vez de descartadas: descartar deixaria quase todos os municípios "sem dados" até haver 3 anos de SINISA.
- **Consequências:** o termômetro volta a refletir dados de 2023 em diante assim que o data-refresh rodar. Se o Ministério mudar o layout das planilhas, a fonte fica "indisponível" ou "última versão válida", sem derrubar o pipeline, e os padrões de cabeçalho podem ser ajustados no YAML sem mexer no código.

## ADR-011. Supressão de contagens pequenas

- **Decisão:** médias anuais de óbitos hospitalares por DRSAI abaixo de 5 por município são publicadas como "menos de 5" (`null` com explicação). Contagens de pessoas quilombolas com todas as células sob sigilo ficam `null`.
- **Consequências:** nenhuma saída permite inferir casos individuais em municípios pequenos.
