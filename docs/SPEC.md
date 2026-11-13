# PROMPT MASTER: Territórios com Sede
### Observatório de água e saneamento do Instituto SDW (institutosdw.org)

> **Como usar:** abra o Claude Code numa pasta vazia e cole este documento inteiro como primeira mensagem. Ele foi escrito para você (Claude Code) trabalhar de forma autônoma do início ao fim, sem depender de respostas humanas.

---

## 0. SEU PAPEL E MODO DE TRABALHO

Você é ao mesmo tempo **tech lead, engenheiro de dados, desenvolvedor full-stack, cientista de dados e revisor crítico** deste projeto. Vai construir, testar, validar, criticar e melhorar a plataforma **sozinho**.

**Regras de autonomia:**

1. **Não pare para perguntar.** Diante de uma dúvida, escolha a opção mais conservadora e mais alinhada a este documento, registre a decisão em `docs/DECISIONS.md` (formato ADR curto: contexto → decisão → alternativas → consequências) e siga em frente. Dúvidas que realmente precisam de um humano vão para `docs/QUESTIONS.md`, sem bloquear o trabalho.
2. **Trabalhe em marcos (seção 10).** Cada marco tem critérios de aceite. Só avance quando todos passarem.
3. **Ciclo obrigatório em cada marco:** planejar → implementar → testar → validar dados → **revisão crítica** (seção 11) → corrigir → atualizar `docs/PROGRESS.md` → commit.
4. **Nunca invente dados.** Se uma fonte estiver fora do ar, mudou de formato ou não tem o recorte necessário, marque como `indisponível` com o motivo, registre em `docs/DATA_SOURCES.md` e siga com o resto. Nenhum número pode aparecer na interface sem fonte rastreável.
5. **Verifique tudo o que este documento afirma sobre fontes externas.** URLs, códigos de indicadores e formatos citados aqui são **pontos de partida**, não verdades. Confirme cada um antes de depender dele e corrija o documento de fontes quando divergir.
6. **Use subagentes** para pesquisa paralela de fontes e para as revisões críticas, quando estiverem disponíveis.
7. **Commits pequenos e frequentes**, com mensagens claras em português, usando Conventional Commits (`feat:`, `fix:`, `data:`, `docs:`, `test:`).
8. **Ao terminar**, produza `HANDOFF.md` (seção 12) e pare.

**Primeira ação:** crie o repositório git, o `CLAUDE.md` (resumo operacional deste documento: regras, comandos, estrutura) e `docs/SPEC.md` (este documento na íntegra, que vira a fonte da verdade). Depois crie `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/QUESTIONS.md`, `docs/DATA_SOURCES.md` e `docs/METODOLOGIA.md`.

---

## 1. CONTEXTO

**Instituto SDW** (institutosdw.org), sede em Salvador/BA, com atuação em Salvador (Itacaranha) e em São Gonçalo do Amarante/CE (Croatá). É ligado ao grupo SDW, que leva água potável e saneamento a comunidades rurais, indígenas e quilombolas em mais de 16 estados. A missão combina educação ambiental (crianças, jovens e lideranças), água potável e saneamento, com tecnologias sociais como filtros, captação de água da chuva e unidades Aquatorre com energia solar.

**Frase-missão (use na plataforma):** *"Que ninguém adoeça por causa da água que bebe."*

**Histórico:** o Instituto já teve um painel chamado "Cidades com Sede". A nova plataforma se chama **Territórios com Sede**, porque inclui comunidades que não são "cidades" (quilombolas, indígenas, ribeirinhas, rurais, assentamentos).

### Narrativa (use na home e na página "Sobre")

- **Manifesto:** "No Brasil, a sede tem endereço. E quase sempre ele está fora das estatísticas."
- **Problema:** os dados de saneamento existem, mas estão espalhados em dezenas de sistemas públicos e numa linguagem que não serve a quem decide nem a quem sofre. As médias municipais escondem os territórios que mais precisam.
- **Insight:** a falta de saneamento é um **gasto público invisível** (internações no SUS, água tratada que vaza, dias de trabalho e de escola perdidos). O país já paga pelo saneamento que não tem, só que paga em forma de doença.
- **Solução, em três verbos:**
  - **Ver:** a situação de cada município e das comunidades dentro dele.
  - **Calcular:** quanto o território economizaria eliminando as doenças de veiculação hídrica.
  - **Agir:** onde o investimento gera mais impacto, com acompanhamento de resultado.
- **Por que agora:** faltam 7 anos para as metas de 2033 do Marco Legal do Saneamento (Lei 14.026/2020: 99% de água e 90% de esgoto). O Censo 2022 contou a população quilombola pela primeira vez. Novos governos estaduais e federal elaboram os PPAs 2028–2031 ao longo de 2027.

### Públicos e a pergunta de cada um

| Público | Pergunta |
|---|---|
| Cidadão | Como está o meu território e por que isso me afeta? |
| Gestor público, câmara, MP, imprensa | Onde estou perdendo dinheiro e o que priorizo? |
| Instituto SDW, financiadores, parceiros | Onde um projeto gera mais impacto por real investido? |
| Escolas e educadores | Como ensinar água e saneamento a partir da realidade local? |

---

## 2. RESTRIÇÕES INEGOCIÁVEIS

1. **Custo zero de operação.** Nenhum serviço pago e nenhum cartão de crédito. Só planos gratuitos estáveis e software livre. Toda dependência de plano gratuito precisa de um plano de saída documentado (formatos abertos, portabilidade).
2. **Sem servidor rodando.** O site é estático. Os dados são processados em lote (GitHub Actions) e servidos como arquivos.
3. **Dados abertos e metodologia aberta.** O repositório será público. Todo indicador tem fonte, data de referência, fórmula e limitações documentadas.
4. **Zero número inventado.** Estimativas são rotuladas como estimativas, com intervalo ou premissas visíveis. Valores indisponíveis aparecem como "sem dado", nunca como zero.
5. **Ética com povos e comunidades tradicionais.** Veja a seção 7.
6. **LGPD.** Nenhum dado pessoal. Analytics sem cookies. Logs de busca anonimizados e agregados.
7. **Acessibilidade:** WCAG 2.1 AA, mobile-first, funcionamento em conexões lentas (orçamento de performance na seção 8).
8. **Idioma:** interface e documentação em **português do Brasil**, com linguagem simples. Código e identificadores em inglês.
9. **Escala nacional desde o design.** Esta entrega implementa a **Bahia**, mas tudo é parametrizado por UF. Rodar para outro estado precisa ser uma mudança de configuração, não de código.

---

## 3. ESCOPO DESTA ENTREGA

### Dentro

**Plataforma completa e funcional para os 417 municípios da Bahia** (verifique o número), com:

- Mapa interativo com camadas de indicadores e de comunidades/territórios
- Ficha completa de cada município
- Calculadora de economia / SROI
- Termômetro 2033 (distância até as metas do Marco Legal)
- Índice de prioridade territorial
- Perguntas guiadas e rankings
- Busca unificada
- FAQ, metodologia e página "Sobre"
- Card compartilhável por município ("Seu território tem sede?")
- Módulo "Territórios com Sede na escola" (versão inicial)
- Área de dados abertos (downloads CSV/Parquet + dicionário de dados)
- Pipeline automatizado de atualização (GitHub Actions)
- Infraestrutura de "aprendizado com o uso" (seção 6)
- Assistente de IA **plugável e desligado** por padrão (seção 6)

**Prova de escala:** no último marco, rode o pipeline também para o **Ceará** (obrigatório pelo menos São Gonçalo do Amarante, que tem projeto do Instituto em Croatá) e confirme que nada precisou de alteração no código.

### Fora (fica documentado no roadmap do HANDOFF)

- Expansão para os 27 estados (preparada, não executada)
- Cadastro e monitoramento de projetos SDW (Fase 3), com o modelo de dados já desenhado
- Ativação do assistente de IA (depende de crédito ou plano gratuito do provedor)
- Deploy em produção (exige credenciais humanas: veja o HANDOFF)

---

## 4. ARQUITETURA (CUSTO ZERO)

### Stack recomendada

Pode trocar qualquer item se encontrar opção melhor, desde que registre uma ADR justificando e respeite a seção 2.

| Camada | Tecnologia |
|---|---|
| Pipeline de dados | Python 3.12, `uv`, DuckDB, Polars, GeoPandas. Validação com Pandera. Leitura de `.dbc` do DATASUS com PySUS ou equivalente (verifique a manutenção) |
| Armazenamento | Parquet (analítico) + JSON por município (consumo do site), versionados por data de referência |
| Site | Astro (estático, com ilhas de interatividade), TypeScript, Tailwind ou CSS próprio |
| Mapas | MapLibre GL JS + PMTiles (gerados com tippecanoe ou equivalente) + mapa base gratuito sem chave (OpenFreeMap ou Protomaps) |
| Consultas no navegador | Dados pré-agregados em JSON. DuckDB-WASM só se as perguntas guiadas exigirem (avalie o peso) |
| Busca | MiniSearch (entidades: municípios, comunidades, indicadores) + Pagefind (conteúdo textual) |
| Gráficos | Biblioteca leve e acessível (Observable Plot, uPlot ou SVG próprio) |
| CMS de conteúdo | Markdown no repositório + Decap CMS (FAQ, textos, página da escola) |
| Imagens de compartilhamento | Geradas no build (Satori + resvg ou equivalente), uma por município |
| CI/CD | GitHub Actions: testes a cada PR, pipeline de dados mensal, build e deploy |
| Hospedagem | Cloudflare Pages (preferencial, o site institucional já usa Cloudflare) ou GitHub Pages. Subdomínio: `territorios.institutosdw.org` |
| Aprendizado com o uso | Cloudflare Worker + D1 (plano gratuito), com coleta mínima e anonimizada |
| Analytics | Cloudflare Web Analytics (sem cookies) |
| Testes | pytest, Pandera, Vitest, Playwright, axe-core, Lighthouse CI |

### Estrutura de pastas sugerida

```
/pipeline/           # ingestão, transformação e validação (Python)
  sources/           # um módulo por fonte (download + parse + metadata)
  transform/         # indicadores, calculadora, índice, termômetro
  validate/          # schemas Pandera e checagens de sanidade
  config/            # ufs.yaml, indicadores.yaml, cid_drsai.yaml, pesos_indice.yaml
/data/
  raw/               # gitignored (cache local de downloads)
  processed/         # Parquet versionado (pequeno, por UF)
  public/            # JSON consumido pelo site + downloads abertos
/site/               # Astro
/worker/             # Cloudflare Worker de aprendizado (opcional)
/docs/               # SPEC, METODOLOGIA, DATA_SOURCES, DECISIONS, PROGRESS, QUESTIONS
/.github/workflows/  # ci.yml, data-refresh.yml, deploy.yml, learning-report.yml
```

### Regras do pipeline

- **Chave universal:** código IBGE do município com 7 dígitos. Atenção: o DATASUS usa 6 dígitos (sem o dígito verificador). Crie uma tabela de-para validada.
- **Idempotente e com cache:** rodar duas vezes dá o mesmo resultado, e downloads ficam em cache com checksum.
- **Metadados por arquivo de saída:** fonte, URL, data de coleta, período de referência, versão do pipeline.
- **Resiliência:** se uma fonte falhar, o pipeline mantém a última versão válida daquele indicador, marca como desatualizado e **não derruba o build**.
- **Limites do GitHub Actions:** processe o DATASUS por UF e mês e agregue para município × ano. Não versione arquivos brutos grandes.
- **Atenção:** o GitHub desativa workflows agendados em repositórios públicos sem atividade por 60 dias. O pipeline mensal deve gerar um commit (atualização de dados ou de metadados) para manter o repositório ativo.

---

## 5. FONTES DE DADOS

Para cada fonte: verifique disponibilidade, formato, licença, periodicidade e última atualização, e documente em `docs/DATA_SOURCES.md`. Se uma fonte prioritária falhar, busque alternativa oficial e registre.

| Prioridade | Fonte | Uso | Ponto de partida (verificar) |
|---|---|---|---|
| P0 | **IBGE Localidades e Malhas** | Lista de municípios, geometrias | APIs do IBGE (servicodados.ibge.gov.br) |
| P0 | **IBGE Censo 2022 (SIDRA)** | População; abastecimento de água, esgotamento e lixo por domicílio; recortes indígena e quilombola | API SIDRA (apisidra.ibge.gov.br) |
| P0 | **SNIS (série histórica) e SINISA** (Ministério das Cidades) | Atendimento de água e esgoto, tratamento de esgoto, perdas, tarifas, despesas por m³, investimentos | Portal do Ministério das Cidades / dados.gov.br. Mapeie os indicadores SNIS (ex.: IN055 água, IN056 esgoto, IN046 tratamento, IN049 perdas, confirme os códigos) para os equivalentes SINISA e documente a transição |
| P0 | **DATASUS SIH/SUS** | Internações por DRSAI por município de **residência**: quantidade, valor pago, dias de permanência, idade, óbito hospitalar | FTP do DATASUS (arquivos RD por UF e mês) |
| P1 | **DATASUS SIM** | Óbitos por DRSAI (camada opcional) | FTP do DATASUS |
| P1 | **SISAGUA** | Qualidade da água distribuída (amostras fora do padrão) | OpenDataSUS / dados.gov.br |
| P1 | **S2ID** (Defesa Civil) | Decretos de emergência e calamidade (seca, estiagem, enchente) | Dados abertos do MIDR |
| P1 | **FUNAI** | Terras indígenas (polígonos e situação) | Geoserviços da FUNAI |
| P1 | **INCRA** | Territórios quilombolas e assentamentos | Acervo fundiário do INCRA |
| P1 | **Fundação Cultural Palmares** | Comunidades quilombolas certificadas (por município) | Site da Palmares |
| P1 | **IBGE Censo 2022: localidades indígenas e quilombolas** | Presença e população por município | IBGE |
| P2 | **ICMBio** | RESEX e RDS (proxy de ribeirinhos e extrativistas) | Dados geoespaciais do ICMBio |
| P2 | **CadÚnico** (agregados) | Vulnerabilidade, grupos tradicionais e específicos | Ferramentas de dados agregados do MDS |
| P2 | **ANA** | Segurança hídrica, mananciais, carga de esgoto | Dados abertos da ANA / SNIRH |
| P2 | **SICONFI** (Tesouro) | Finanças municipais, despesa com saneamento | API do SICONFI |
| P2 | **IBGE (renda)** | Renda média para a calculadora | SIDRA |
| P2 | **IPCA** (IBGE ou BCB) | Deflacionar valores monetários | API do BCB ou SIDRA |

**Divergência entre fontes:** SNIS/SINISA é autodeclarado pelos prestadores e o Censo é a medida domiciliar. Mostre os dois quando divergirem mais que um limiar (sugestão: 15 pontos percentuais), com explicação simples. Isso é conteúdo, não erro.

---

## 6. FUNCIONALIDADES (ESPECIFICAÇÃO)

### 6.1 Home
Manifesto, mapa da Bahia em destaque, busca central ("Digite seu município, comunidade ou CEP"), três números de impacto do estado (ex.: pessoas sem esgoto, custo anual das internações por DRSAI, municípios fora do ritmo de 2033) e entradas para Ver, Calcular e Agir.

### 6.2 Mapa
Camadas alternáveis: cobertura de água, esgoto, tratamento, perdas, internações por DRSAI por 10 mil habitantes, custo do déficit per capita, índice de prioridade, termômetro 2033, decretos de seca, terras indígenas, territórios quilombolas, assentamentos e UCs de uso sustentável. Legenda acessível, paletas seguras para daltônicos e tooltip com fonte.

### 6.3 Ficha do município
- Resumo em linguagem simples (texto gerado por **templates determinísticos** a partir dos dados, sem IA em tempo de execução)
- Indicadores com série histórica, comparação com vizinhos, mediana da UF e Brasil, e divergência SNIS × Censo
- Termômetro 2033
- Custo do déficit e atalho para a calculadora já preenchida
- Comunidades e territórios presentes (seção 7)
- Qualidade da água (SISAGUA) e decretos recentes (S2ID)
- Posição no índice de prioridade, com explicação dos componentes
- Tecnologias sociais sugeridas conforme o perfil (seção 6.7)
- Fontes e datas de referência de cada bloco, botão de download e card compartilhável

### 6.4 Calculadora de economia / SROI
**Objetivo:** mostrar quanto o território economizaria se as doenças relacionadas ao saneamento inadequado fossem reduzidas em X%. **Não estima o custo de obras.**

**Componentes (cada um ligável e desligável, com premissa visível):**

| Componente | Cálculo base | Padrão |
|---|---|---|
| Custo hospitalar SUS | Média anual (últimos N anos, deflacionada) do valor pago (SIH) das internações por DRSAI, município de residência | Ligado |
| Produtividade perdida | Dias de internação × renda média diária. Para pacientes < 14 anos, conta um dia de acompanhante adulto | Ligado |
| Dias letivos perdidos | Dias de internação de pacientes de 6 a 17 anos (indicador, não monetizado por padrão) | Ligado (só exibição) |
| Atendimento ambulatorial | Multiplicador sobre internações, **somente** com referência bibliográfica documentada | Desligado |
| Óbitos evitáveis | SIM × anos produtivos × renda (abordagem sensível, texto explicativo obrigatório) | Desligado |

**Doenças (configurável em `cid_drsai.yaml`).** Valide os códigos CID-10 contra a classificação de DRSAI da Funasa e a literatura, e documente a fonte.
- **Núcleo conservador (padrão):** transmissão feco-oral e contato com água. Ponto de partida: A00–A09 (diarreias e gastroenterites infecciosas), B15 (hepatite A), A27 (leptospirose), B65 (esquistossomose), B68–B69 e B76–B83 (helmintíases e teníases).
- **Camada opcional "vetores":** dengue e outras arboviroses, malária, doença de Chagas, leishmanioses, febre amarela. Verifique os códigos vigentes (houve mudanças de codificação para dengue). Explique na interface que a relação com saneamento é mais indireta.

**Parâmetros do usuário:** % de redução (slider de 0 a 100), horizonte (1 a 30 anos), taxa de desconto real (padrão documentado em ADR), e cenários rápidos: 25%, 50%, 100% e **"resultado médio dos projetos SDW: 92%"**. Este último deve trazer o rótulo: *"dado informado pela SDW, em validação independente"*.

**Modo SROI avançado (opcional):** o usuário informa um investimento hipotético e a calculadora devolve:

```
VP = Σ (t = 1..H) [ B × r% × (1 − deadweight) × atribuição × (1 − drop_off)^(t−1) ] / (1 + taxa)^t
SROI = VP / investimento
```

onde B é o benefício anual base. Deadweight, atribuição e drop-off vêm com padrões documentados e explicação em linguagem simples, seguindo os princípios de SROI (Social Value International).

**Saídas:** economia anual, acumulada em valor presente, decomposição por componente, faixa de sensibilidade (mínimo e máximo variando as premissas principais) e um texto pronto para copiar ("Em [município], a redução de X% das DRSAI pode poupar R$ Y por ano..."). Link compartilhável com os parâmetros na URL e exportação em PDF pelo navegador (CSS de impressão).

**Testes obrigatórios:** casos unitários com valores calculados à mão, propriedades (monotonicidade em % de redução, VP zero com 0% de redução, convergência quando a taxa vai a zero) e paridade exata entre o cálculo em Python (pipeline) e em TypeScript (site).

### 6.5 Termômetro 2033
Para água (meta 99%) e esgoto (meta 90%): valor atual, distância até a meta, tendência (regressão sobre os últimos 5 a 8 anos disponíveis, com no mínimo 3 pontos) e ano projetado de atingimento. Classificação: **no ritmo**, **atrasado** ou **sem dados suficientes**. Mostre a incerteza e explique que a projeção é linear e indicativa.

### 6.6 Índice de prioridade territorial
Dimensões, com pesos padrão em `pesos_indice.yaml`:

| Dimensão | Exemplos | Peso padrão |
|---|---|---|
| Déficit de acesso | % sem água adequada, % sem esgoto adequado (Censo) | 30% |
| Carga de saúde | Internações por DRSAI por 10 mil habitantes, custo per capita | 25% |
| Vulnerabilidade social | Renda, CadÚnico, presença de povos e comunidades tradicionais | 20% |
| Risco climático e hídrico | Decretos de seca e enchente nos últimos 5 anos, segurança hídrica (ANA) | 15% |
| Qualidade da água | % de amostras fora do padrão (SISAGUA) | 10% |

- Normalização por percentil, com ranking dentro da UF (e preparado para nacional)
- Tratamento explícito de dado faltante: reponderar e sinalizar, nunca imputar zero
- **Pesos ajustáveis pelo usuário** na interface, com ranking recalculado no navegador
- **Análise de sensibilidade** documentada: quanto o top 20 muda variando os pesos ±10 pontos

### 6.7 "Agir": tecnologias sociais sugeridas
Regras simples e transparentes que associam o perfil do território a tipos de solução: captação de água da chuva e cisternas (semiárido, decretos de seca), filtros e tratamento no ponto de uso (qualidade da água ruim, comunidades sem rede), unidades autônomas de tratamento com energia solar (sem rede de água ou de energia), saneamento rural descentralizado, redução de perdas (perdas altas, contexto urbano) e educação ambiental (sempre). **Sem estimativa de custo.** Cada sugestão traz uma explicação e um contato do Instituto.

### 6.8 Perguntas guiadas e rankings
Um construtor de perguntas por menus: "[Ranking | Lista | Comparação] de [indicador] em [UF ou região intermediária] [filtro: com comunidades quilombolas / semiárido / porte]". Resposta calculada no navegador, com gráfico, tabela e link compartilhável. Ofereça no mínimo 10 perguntas prontas.

### 6.9 Busca unificada
Municípios (com tolerância a acentos e erros de digitação), comunidades e territórios, indicadores, perguntas do FAQ e páginas. CEP → município, via base aberta ou API gratuita sem chave (se não houver fonte estável, documente e deixe desativado). Buscas sem resultado devem sugerir alternativas.

### 6.10 FAQ, metodologia e página "Sobre"
- **FAQ inicial** com no mínimo 20 perguntas (o que é DRSAI, o que é o Marco Legal, por que o SNIS e o Censo divergem, como a calculadora funciona, como usar os dados etc.), editável no Decap CMS.
- **Metodologia:** cada indicador com fórmula, fonte, limitações e data de referência, gerada a partir de `indicadores.yaml` (fonte única da verdade).
- **Sobre:** narrativa, Instituto SDW e como contribuir ou corrigir dados (formulário via GitHub Issues).

### 6.11 Card compartilhável
Imagem 1200×630 por município, gerada no build: nome, 3 números-chave, frase "Seu território tem sede?" e a URL. Inclua as meta tags Open Graph corretas.

### 6.12 "Territórios com Sede na escola" (v1)
Uma página por município em versão simplificada para estudantes, mais 3 roteiros de atividade para professores (anos finais do ensino fundamental e ensino médio) que usam os dados do próprio município. Formato imprimível.

### 6.13 Dados abertos
Downloads por UF e por município (CSV e Parquet), dicionário de dados, licença (sugestão: CC BY 4.0 para os dados derivados, sujeita às licenças das fontes; verifique), citação sugerida e changelog dos dados.

### 6.14 Aprendizado com o uso (custo zero)
- **Worker** (Cloudflare, plano gratuito) que recebe eventos anônimos: termo buscado sem resultado, pergunta guiada montada, cenário de calculadora usado. Nada de IP, de identificador pessoal ou de cookie.
- **Workflow mensal** que lê os agregados e abre uma Issue no GitHub "Relatório mensal de aprendizado", com sugestões de novas perguntas para o FAQ, termos que a busca deveria entender e indicadores mais procurados. **Um humano aprova antes de publicar.**
- O site funciona 100% sem o Worker. O Worker é um aprimoramento opcional, ativado por variável de ambiente.

### 6.15 Assistente de IA (plugável, desligado)
- Interface de chat e camada de provedor abstrata (`AssistantProvider`) com implementações de exemplo.
- **Regra de ouro:** responde só com base nos dados da plataforma (ferramentas que consultam os JSON e Parquet), sempre citando fonte e data, e diz "não sei" quando o dado não existe.
- Feature flag `ASSISTANT_ENABLED=false` por padrão. Documente no HANDOFF como ligar (créditos para ONGs, planos gratuitos) e os riscos.

---

## 7. POVOS E COMUNIDADES TRADICIONAIS: REGRAS ÉTICAS

1. **Nível de território, nunca ponto exato** de aldeias, casas ou povos isolados e de recente contato. Use polígonos oficiais já públicos (terras indígenas, territórios quilombolas, assentamentos, UCs) e contagens agregadas por município.
2. Mostre o **status oficial** (ex.: terra indígena declarada ou homologada; quilombo certificado ou titulado) com a fonte.
3. Linguagem respeitosa, com nomes oficiais e autodenominação quando disponível.
4. Destaque a **desigualdade escondida** quando houver dado (ex.: saneamento da população quilombola × média do município no Censo 2022), sempre com contexto.
5. Página explicando os princípios (Convenção 169 da OIT, consulta livre, prévia e informada) e um canal para comunidades e organizações representativas pedirem correção ou retirada de informação.
6. Registre em `docs/QUESTIONS.md` a recomendação de validar a camada com organizações representativas (ex.: CONAQ, APIB, COIAB) antes do lançamento público.

---

## 8. DESIGN, ACESSIBILIDADE E PERFORMANCE

- **Identidade:** inspire-se no site institucional (institutosdw.org): tom direto e próximo, foco em comunidade e água. Crie tokens de design próprios (cores, tipografia, espaçamento) num arquivo único. Use paletas sequenciais e divergentes acessíveis para os mapas. Tipografia livre (Google Fonts ou self-hosted).
- **Linguagem:** frases curtas, números com contexto ("1 em cada 3 moradores"), unidades sempre explícitas, formato brasileiro (R$ 1.234,56; 12,5%).
- **Acessibilidade:** WCAG 2.1 AA, navegação por teclado, alternativa em tabela para todo mapa e gráfico, contraste validado e `prefers-reduced-motion`.
- **Orçamento de performance:** página da ficha com menos de 200 KB de JS, Lighthouse ≥ 90 nas quatro categorias em mobile, e site utilizável em 3G (dados carregados sob demanda).
- **SEO:** uma URL por município (`/municipio/ba/salvador`), sitemap, dados estruturados e meta tags.

---

## 9. QUALIDADE E VALIDAÇÃO DE DADOS

**Checagens automáticas (o pipeline falha se não passarem):**
- Número de municípios da UF bate com o IBGE (BA = 417, verificar), e todos os códigos são válidos e únicos
- População total da UF bate com o Censo 2022 (tolerância zero para a soma)
- Percentuais entre 0 e 100, e valores monetários não negativos
- Tabela de-para de 6 para 7 dígitos cobre 100% dos códigos do SIH
- Séries históricas sem saltos absurdos (alerta acima de um limiar configurável, ex.: variação maior que 50% ao ano, que gera aviso e não erro)

**Checagens de plausibilidade (relatório em `docs/VALIDATION_REPORT.md`):**
- Confira por amostragem (no mínimo 5 municípios, incluindo Salvador e São Gonçalo do Amarante/CE) os totais de internações do pipeline contra o TabNet/DATASUS e documente as diferenças
- Compare cobertura SNIS/SINISA × Censo para todos os municípios e liste os maiores divergentes
- Identifique e documente municípios sem dado em cada fonte
- Revise manualmente o top 10 e o bottom 10 do índice de prioridade: o resultado faz sentido? Por quê?

---

## 10. MARCOS E CRITÉRIOS DE ACEITE

| Marco | Entrega | Critério de aceite |
|---|---|---|
| **M0. Fundação** | Repositório, CLAUDE.md, docs, estrutura, CI básico, configs YAML | `make test` e `make lint` passam, e o CI roda verde |
| **M1. Investigação de fontes** | `DATA_SOURCES.md` com cada fonte verificada (status, formato, URL real, licença, última atualização) | Todas as fontes P0 acessíveis ou com alternativa documentada |
| **M2. Pipeline P0 (BA)** | Municípios, malhas, Censo, SNIS/SINISA, SIH processados e validados | Checagens da seção 9 passam e os Parquet e JSON são gerados |
| **M3. Indicadores e cálculos** | Indicadores, custo do déficit, calculadora (Python), termômetro, índice | Testes unitários e de propriedade passam, e `VALIDATION_REPORT.md` está preenchido |
| **M4. Site núcleo** | Home, mapa, ficha, busca, metodologia | Playwright cobre os fluxos principais e axe não aponta violações graves |
| **M5. Calculadora e perguntas guiadas** | Calculadora em TS com paridade exata com a versão Python, e construtor de perguntas | Testes de paridade passam e os links compartilháveis funcionam |
| **M6. Camadas P1/P2 e comunidades** | SISAGUA, S2ID, FUNAI, INCRA, Palmares, ICMBio, CadÚnico, ANA, SICONFI | Regras da seção 7 cumpridas, e camadas indisponíveis estão documentadas |
| **M7. Conteúdo e extras** | FAQ (≥ 20), escola, dados abertos, cards OG, CMS, Worker, assistente desligado, workflows | Build completo sem erros e Lighthouse ≥ 90 |
| **M8. Prova de escala e endurecimento** | Pipeline rodado para o CE, revisão crítica final e HANDOFF | Nenhuma alteração de código necessária para o CE, e o HANDOFF está completo |

---

## 11. PROTOCOLO DE REVISÃO CRÍTICA

Ao fim de cada marco (M2 em diante), rode uma revisão adversarial, de preferência com um subagente por persona. Cada persona deve encontrar **no mínimo 3 problemas reais** ou justificar por escrito por que não há nenhum:

1. **Cientista de dados cético:** os números estão certos? Há dupla contagem, unidade errada, viés de dado faltante, deflação incorreta, município de internação no lugar do de residência?
2. **Especialista em saneamento:** os indicadores e as metas estão interpretados corretamente? A transição SNIS → SINISA foi bem tratada?
3. **Gestor municipal do interior da Bahia:** eu entendo a ficha em 30 segundos? Isso me ajuda a decidir algo? Funciona no meu celular com 3G?
4. **Liderança quilombola ou indígena:** a forma como minha comunidade aparece é respeitosa e segura? Algo expõe a gente?
5. **Jornalista:** consigo tirar uma pauta verificável daqui, com fonte citável?
6. **Auditor de custo zero e segurança:** existe alguma dependência que pode gerar cobrança ou quebrar? Há segredos no repositório? Algum dado pessoal?
7. **Especialista em acessibilidade:** dá para usar tudo com teclado e leitor de tela?

Registre os achados e as correções em `docs/REVIEWS/M<n>.md`. Corrija todos os problemas graves antes de avançar, e os demais vão para o backlog no PROGRESS.

Além disso, **tire screenshots com Playwright** (mobile e desktop) das páginas principais a cada marco de interface, olhe para elas e critique o visual e a hierarquia de informação como um designer exigente.

---

## 12. ENTREGA FINAL: HANDOFF.md

Ao concluir o M8, escreva `HANDOFF.md` em linguagem simples para uma equipe não técnica, contendo:

1. **O que foi construído:** resumo, prints e como rodar localmente (`make dev`).
2. **Passo a passo para publicar,** com o que exige uma pessoa: criar a conta gratuita no Cloudflare e conectar o repositório, configurar o subdomínio `territorios.institutosdw.org`, tornar o repositório público no GitHub, configurar os secrets e ativar o Worker (opcional).
3. **Como a plataforma se mantém sozinha:** o calendário dos workflows e o que fazer quando um deles falhar.
4. **Como editar conteúdo** (FAQ, textos, escola) pelo CMS.
5. **Estado de cada fonte de dados** e limitações conhecidas.
6. **Decisões que precisam de validação humana** (conteúdo de `QUESTIONS.md`), incluindo a validação da camada de comunidades com organizações representativas e a revisão da metodologia da calculadora por um especialista em economia da saúde.
7. **Roadmap:**
   - Fase 1: 27 estados (o que rodar, tempo estimado do pipeline, limites do plano gratuito)
   - Fase 2: relatórios estaduais em PDF e alertas
   - Fase 3: cadastro de projetos SDW com linha de base e monitoramento de impacto (modelo de dados já proposto), incluindo como validar de forma independente a redução de 92% informada pela SDW
   - Como ativar o assistente de IA
8. **Riscos e plano de saída** para cada serviço gratuito usado.

---

## 13. DEFINIÇÃO DE PRONTO (CHECKLIST FINAL)

- [ ] Os 417 municípios da BA têm ficha completa, com "sem dado" explícito onde faltar
- [ ] Calculadora com paridade Python × TS, testes de propriedade e cenário SDW 92% rotulado
- [ ] Termômetro 2033 e índice de prioridade com pesos ajustáveis e análise de sensibilidade
- [ ] Camadas de comunidades seguindo as regras da seção 7
- [ ] Busca, perguntas guiadas, FAQ (≥ 20), metodologia, escola, dados abertos e cards OG
- [ ] Pipeline mensal automatizado, idempotente e resiliente a falhas de fonte
- [ ] CI verde: testes, lint, Playwright, axe e Lighthouse ≥ 90 em mobile
- [ ] Nenhuma dependência paga e nenhum segredo no repositório
- [ ] O CE roda sem alteração de código
- [ ] Revisões críticas M2–M8 registradas, e todos os problemas graves resolvidos
- [ ] `VALIDATION_REPORT.md` e `HANDOFF.md` completos

**Comece agora pelo M0. Bom trabalho.**
