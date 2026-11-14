# Territórios com Sede — guia de entrega

Este documento é para a equipe do Instituto SDW. Ele explica o que foi construído, o que falta uma pessoa fazer
para publicar, como a plataforma se mantém sozinha e o que ainda precisa de decisão humana.

> *Que ninguém adoeça por causa da água que bebe.*

---

## 1. O que foi construído

Uma plataforma na internet que mostra, para cada município, como estão a água, o esgoto e a saúde, quanto custa
não ter saneamento e onde agir primeiro. Nesta entrega: **os 417 municípios da Bahia** e, como prova de que funciona
para qualquer estado, **os 184 municípios do Ceará** (incluindo São Gonçalo do Amarante, onde fica Croatá).

| Página | O que faz |
|---|---|
| Início | Manifesto, mapa da Bahia, busca e três números do estado |
| Ficha do município (601) | Resumo em linguagem simples, indicadores com comparação, termômetro 2033, saúde (internações e óbitos), "Quanto custa" (conta de impacto em camadas), comunidades, atuação do Instituto SDW, sugestões de soluções, fontes, downloads e card para redes sociais |
| Panorama estadual (`/estado/ba`, `/estado/ce`) | Números do estado, meta de 2033, municípios mais populosos atrasados, tabela por região, água perdida, fontes; botão "Salvar em PDF" |
| Mapa | Camadas de água, esgoto, perdas, metas de 2033, Semiárido, terras indígenas e reservas extrativistas, com tabela alternativa |
| Calculadora | Quanto o município economizaria reduzindo doenças ligadas à água (com modo SROI) |
| Perguntas | Monte perguntas aos dados por menus; 12 perguntas prontas |
| Prioridades | Índice de prioridade com pesos ajustáveis |
| Escola | Página de cada município para estudantes e 3 roteiros para professores |
| Dados abertos | Downloads em CSV e Parquet, dicionário, licença, citação e consulta SQL no navegador (`/dados/sql`) |
| Metodologia, FAQ (24 perguntas), Sobre, Povos e comunidades tradicionais | Transparência e participação |

Prints: `docs/img/home.png`, `docs/img/ficha-celular.png`, `docs/img/mapa.png`, `docs/img/calculadora.png`,
`docs/img/perguntas.png`.

**Qualidade verificada:** 77 testes do pipeline, 416 testes do site (inclui a conferência de que a calculadora dá
exatamente o mesmo resultado em Python e no navegador, em 248 casos), 54 testes de navegação em computador e
celular com verificação automática de acessibilidade, e nota Lighthouse de 90 ou mais (celular) nas quatro
categorias em todas as páginas medidas.

### Como rodar no seu computador

Precisa de Python 3.12+ com [uv](https://docs.astral.sh/uv/) e Node 22.

```bash
make setup
```

```bash
make data UF=BA
```

```bash
make dev
```

O site abre em http://localhost:4321.

---

## 2. Atenção: de onde vieram os dados desta versão

A plataforma foi construída num ambiente que **não conseguia acessar os sites do governo** (IBGE, DATASUS, gov.br,
Banco Central). Por isso:

- Parte dos dados veio de **cópias públicas rastreáveis** dos dados oficiais (Base dos Dados e pacote geobr, do
  Ipea). Os valores são os oficiais; cada arquivo registra de onde veio. Conferimos, por exemplo, que a população
  somada bate exatamente com o total oficial do Censo 2022 nos dois estados.
- **Ficaram sem dado nesta versão**, porque não há cópia pública: internações no SUS (que alimentam a
  calculadora e a dimensão "saúde" do índice), água e esgoto do Censo 2022, renda e pessoas indígenas do Censo,
  qualidade da água (SISAGUA), decretos de seca (S2ID), territórios quilombolas (INCRA), comunidades certificadas
  (Palmares), CadÚnico e finanças municipais (SICONFI).
- O pipeline já está programado para buscar todas essas fontes oficiais. **Na primeira execução no GitHub Actions
  (que tem internet aberta), a maioria delas deve ser preenchida automaticamente.** Algumas (SISAGUA, S2ID,
  INCRA, Palmares, CadÚnico, SICONFI) ainda precisam de um leitor específico (veja o roadmap).
- Enquanto as internações não entrarem, o **índice de prioridade não é publicado** (faltam dimensões). Preferimos
  não mostrar um ranking incompleto.

O site diz isso com clareza onde falta dado ("sem dado", "ainda não processado"), nunca mostra zero no lugar.

---

## 3. Passo a passo para publicar (precisa de uma pessoa)

Tudo abaixo usa **planos gratuitos**. Nenhum pede cartão de crédito.

### 3.1 Colocar o código no GitHub

1. Crie (ou use) a organização do Instituto no GitHub e um repositório chamado `territorios-com-sede`.
2. Envie este repositório para lá (uma pessoa técnica faz isso em minutos com `git remote add` e `git push`).
3. Se o endereço for diferente de `github.com/institutosdw/territorios-com-sede`, ajuste em três lugares:
   `site/src/lib/site.ts`, `site/public/admin/config.yml` e a variável `PUBLIC_REPO_URL` (passo 3.3).
4. **Torne o repositório público** (Settings → General → Danger Zone → Change visibility). Isso deixa os minutos
   do GitHub Actions gratuitos e ilimitados e cumpre a regra de dados e metodologia abertos.

### 3.2 Rodar a primeira atualização de dados

1. No GitHub, abra a aba **Actions** → **Atualização mensal de dados** → **Run workflow**.
2. A primeira vez é longa por causa do SIH (internações): o pipeline precisa baixar cerca de 1.600 arquivos do
   DATASUS para 5 anos de 27 estados (é assim que se contam moradores internados em outros estados). Se passar do
   limite de 6 horas, rode de novo: o que já foi baixado fica guardado (num "Release" chamado `sih-extracts`) e a
   execução continua de onde parou. Também dá para marcar "Pular o SIH" para publicar rápido e rodar o SIH depois.
3. Ao final, o workflow salva os dados atualizados no repositório e o site é publicado.
4. Confira o arquivo `docs/VALIDATION_REPORT.md`, que é regenerado: ele mostra o que veio de cada fonte. Faça a
   conferência por amostragem das internações com o TabNet (o relatório explica como).

### 3.3 Publicar o site no Cloudflare Pages (recomendado)

1. Crie uma conta gratuita em cloudflare.com (o site institucional já usa Cloudflare, então pode ser a mesma).
2. Em **My Profile → API Tokens**, crie um token com permissão "Cloudflare Pages: Edit". Anote também o
   **Account ID** (aparece na página inicial da conta).
3. No GitHub, em **Settings → Secrets and variables → Actions**:
   - *Secrets*: `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID`.
   - *Variables* (opcionais): `SITE_URL` (padrão `https://territorios.institutosdw.org`), `PUBLIC_REPO_URL`,
     `PUBLIC_CF_BEACON_TOKEN` (estatísticas sem cookies, passo 3.5).
4. Rode o workflow **Deploy** (Actions → Deploy → Run workflow). Ele cria o projeto `territorios-com-sede`.
5. **Plano B sem Cloudflare:** publicar no **GitHub Pages**. Só funciona com repositório público (no plano
   gratuito). Ative em Settings → Pages → Source: GitHub Actions e crie a variável `ENABLE_GITHUB_PAGES` = `true`.
   Sem os secrets do Cloudflare e sem essa variável, o Deploy só gera o site e não publica (fica verde).

### 3.4 Configurar o endereço `territorios.institutosdw.org`

1. No Cloudflare, abra o projeto do Pages → **Custom domains** → **Set up a custom domain** →
   `territorios.institutosdw.org`. Como o domínio já está no Cloudflare, o registro DNS é criado sozinho.
2. Aguarde alguns minutos pelo certificado HTTPS.

### 3.5 Estatísticas de acesso sem cookies (opcional)

No Cloudflare: **Analytics & Logs → Web Analytics → Add a site**. Copie o token e salve como variável
`PUBLIC_CF_BEACON_TOKEN` no GitHub. Não usa cookies nem coleta dados pessoais.

### 3.6 Ativar o Worker de aprendizado (opcional)

O site funciona 100% sem isto. O Worker conta, de forma anônima, buscas sem resultado e perguntas montadas, e
todo mês abre uma Issue no GitHub com sugestões (só termos repetidos 5 vezes ou mais; números longos mascarados).

1. Uma pessoa técnica, na pasta `worker/`: `npx wrangler login`, depois `npx wrangler d1 create territorios-aprendizado`
   (copie o `database_id` para `wrangler.toml`), `npm run db:init` e `npx wrangler deploy`.
2. Crie uma senha longa e salve com `npx wrangler secret put REPORT_TOKEN`.
3. No GitHub: variável `PUBLIC_LEARNING_ENDPOINT` = `https://<seu-worker>.workers.dev/event`;
   variável `LEARNING_REPORT_URL` = `https://<seu-worker>.workers.dev/report`; secret `LEARNING_REPORT_TOKEN` =
   a mesma senha. Rode o Deploy de novo.

---

## 4. Como a plataforma se mantém sozinha

| Quando | O que acontece | Workflow |
|---|---|---|
| Todo dia 5, 03:17 (Brasília) | Busca as versões mais recentes das fontes, valida, salva e publica | Atualização mensal de dados → Deploy |
| Todo dia 1º | Abre a Issue "Relatório mensal de aprendizado" (se o Worker estiver ativo) | Relatório mensal de aprendizado |
| A cada mudança no código | Roda todos os testes, acessibilidade e Lighthouse | CI |
| Mensal | Abre pedidos de atualização de dependências | Dependabot |

O workflow mensal **sempre** gera um registro no repositório. Isso impede que o GitHub desative os agendamentos
(ele desliga agendamentos de repositórios públicos sem atividade por 60 dias).

**Se uma fonte falhar**, o site não cai: a última versão válida é mantida e marcada como "desatualizada".
**Se a validação falhar** (por exemplo, a população somada não bater com o total oficial), aquela UF não é
publicada e o workflow fica vermelho.

**O que fazer quando um workflow ficar vermelho:**
1. Abra Actions, clique na execução e veja o passo em vermelho. A mensagem diz qual fonte ou checagem falhou.
2. Fonte fora do ar: espere alguns dias e rode de novo (Run workflow). Nada precisa ser feito no site.
3. Fonte mudou de formato ou de endereço: uma pessoa técnica ajusta `pipeline/config/sources.yaml` (os endereços
   ficam todos ali) ou o leitor da fonte em `pipeline/sources/`.
4. Validação falhou: não publique por cima. Peça a uma pessoa técnica para olhar o `_validation.json` da UF.

---

## 5. Como editar conteúdo (FAQ, roteiros da escola)

**Pelo navegador (Decap CMS):** em `territorios.institutosdw.org/admin`. Cada edição vira uma proposta de mudança
(pull request) que alguém aprova antes de ir ao ar. Para o login funcionar, o Decap precisa de um "provedor de
login" do GitHub: a opção gratuita é um pequeno Worker do Cloudflare (por exemplo, o projeto aberto
`sveltia-cms-auth` ou equivalente); depois, preencha `base_url` em `site/public/admin/config.yml`.

**Direto no GitHub:** os textos são arquivos simples em `site/src/content/faq/` (uma pergunta por arquivo) e
`site/src/content/escola/` (um roteiro por arquivo). Clique no lápis, edite e salve: o site é republicado.

**Retirar informação a pedido de uma comunidade:** acrescente o código em `pipeline/config/retiradas.yaml` e salve.
Na publicação seguinte a informação some das fichas, do mapa, dos downloads e do assistente.

---

## 6. Estado de cada fonte de dados

Resumo (detalhes em `docs/DATA_SOURCES.md` e na página Dados abertos):

| Fonte | Situação nesta versão |
|---|---|
| IBGE: municípios, malhas, população 2022, destino do lixo, quilombolas, cor ou raça | Em uso (cópia pública rastreável) |
| SNIS 1995–2022 (água, esgoto, tratamento, perdas) | Em uso (cópia pública) |
| SINISA (sucessor do SNIS, a partir de 2023) | Leitor pronto (ADR-012); entra no GitHub Actions. A troca de sistema é sinalizada nas projeções |
| DATASUS SIH (internações) | Programado; entra na primeira execução no GitHub Actions |
| Censo 2022: água, esgoto, renda, pessoas indígenas | Programado (descoberta automática no SIDRA); entra no GitHub Actions |
| IPCA | Em uso, mas a cópia termina em 07/2024; a fonte oficial (Banco Central) entra no GitHub Actions |
| FUNAI terras indígenas, reservas extrativistas e RDS (CNUC), Semiárido, ANA Atlas Esgotos | Em uso (cópias públicas) |
| SIM (óbitos), SISAGUA (qualidade da água), S2ID (decretos), Monitor de Secas, Censo Escolar, SICONFI | Leitores prontos (ADR-014); entram no GitHub Actions. Testados só com dados sintéticos: o primeiro data-refresh é o teste com os arquivos oficiais |
| INCRA, Palmares, CadÚnico | Indisponíveis, com motivo registrado; precisam de leitor próprio |

**Limitações conhecidas:** dados do SNIS são autodeclarados pelos prestadores; a população quilombola da cópia
pública é um mínimo (sigilo do IBGE); o termômetro é uma projeção linear indicativa; a calculadora não estima o
custo de obras e mostra um teto (supõe custo constante e efeito desde o primeiro ano).

---

## 7. Decisões que precisam de uma pessoa

A lista completa está em `docs/QUESTIONS.md`. As mais importantes:

1. **Validar a camada de povos e comunidades com organizações representativas** (CONAQ, APIB, COIAB e
   organizações regionais como a APOINME) antes do lançamento público. Definir quem fará o contato.
2. **Revisão da metodologia da calculadora por um especialista em economia da saúde** (componentes, renda de
   referência, deadweight, atribuição, drop-off, taxa de desconto de 8,5%).
3. **Validação independente do resultado de 92% informado pela SDW** (ver Fase 3 abaixo). Até lá, o cenário
   aparece sempre com o rótulo "dado informado pela SDW, em validação independente".
4. **Confirmar a lista de doenças (CID-10)** na publicação original da Funasa.
5. **Confirmar o canal oficial de correção e retirada** (`contato@institutosdw.org`), nomear uma pessoa responsável
   e registrar o prazo de resposta de 15 dias.
6. **Licença das cópias `_bdpro` da Base dos Dados**: confirmar com a Base dos Dados ou desligá-las.

---

## 8. Roadmap

### Fase 1: os 27 estados

- **O que fazer:** acrescentar as UFs em `pipeline/config/ufs.yaml` (sigla, código, número de municípios,
  população do Censo 2022, preposição). Nenhuma mudança de código: o Ceará foi rodado assim nesta entrega.
- **Tempo estimado do pipeline:** sem o SIH, cerca de 1 minuto por UF depois que os arquivos nacionais estão em
  cache. A primeira carga do SIH é a parte pesada (estimativa de várias horas; dividir em execuções por grupos de
  UFs). Depois, cada mês baixa só os meses novos.
- **Limites do plano gratuito a observar:** o Cloudflare Pages aceita até 20 mil arquivos por publicação; com 5.570
  municípios (ficha, página da escola, card, JSON e CSV) passaria disso. Plano: juntar os CSVs por UF em um arquivo
  compactado e gerar os cards em lotes ou sob demanda. O repositório cresce cerca de 1,6 MB por UF por atualização;
  guardar o histórico antigo em Releases em vez de commits.
- Fazer leitores para INCRA, Palmares e CadÚnico. (SINISA, SIM, SISAGUA, S2ID, Monitor de Secas, Censo Escolar e
  SICONFI já têm leitor; conferir o primeiro resultado de cada um no `.meta.json`.)

### Fase 2: relatórios estaduais em PDF e alertas

- Relatório por UF: **feito** como panorama estadual imprimível (`/estado/{uf}`). Próximo passo: folha A4 por
  município para reuniões.
- Alertas por e-mail ou RSS quando um município muda de situação no termômetro ou recebe novos dados.

### Fase 3: projetos SDW com linha de base e monitoramento

Modelo de dados proposto (arquivos abertos, um por projeto, sem dados pessoais):

| Tabela | Campos principais |
|---|---|
| `projeto` | id, nome, tecnologia (filtro, cisterna, Aquatorre, saneamento), município (código IBGE), território (código FUNAI/INCRA/CNUC, se houver e com consentimento), data de início, população atendida, financiador |
| `linha_base` | projeto, indicador (ex.: casos de diarreia em menores de 5 anos na unidade de saúde de referência, faltas escolares, qualidade da água no ponto de uso), valor, período, fonte, método de coleta |
| `acompanhamento` | projeto, indicador, valor, período, fonte, observações |
| `comparacao` | projeto, área de comparação (comunidades semelhantes sem o projeto), indicador, valores |

**Como validar de forma independente a redução de 92%:** definir antes os indicadores e o período; medir a linha de
base antes da instalação; acompanhar por pelo menos 12 meses (para cobrir a sazonalidade); comparar com
comunidades semelhantes sem o projeto (diferença em diferenças); usar dados de saúde de fontes externas ao projeto
(unidade básica de saúde, SIH e e-SUS agregados); e entregar a análise a um avaliador externo (universidade ou
instituto de pesquisa), publicando o protocolo antes dos resultados.

### Como ativar o assistente de IA

O assistente está pronto e **desligado**. Ele responde só com os dados da plataforma, cita a fonte e diz "não sei"
quando o dado não existe.

1. Ative o Worker (passo 3.6).
2. Obtenha uma chave de API da Anthropic (há programas de créditos para organizações sem fins lucrativos; consulte a
   Anthropic). **Defina um limite de gasto mensal no painel da Anthropic** antes de ligar.
3. `npx wrangler secret put ANTHROPIC_API_KEY`; em `wrangler.toml`, `ASSISTANT_ENABLED = "true"` (e, se quiser
   reduzir custo, troque `ASSISTANT_MODEL` por um modelo mais barato e ajuste `ASSISTANT_DAILY_LIMIT`).
4. No GitHub, variável `PUBLIC_ASSISTANT_ENABLED` = `true` e rode o Deploy. A página fica em `/assistente`.

**Riscos:** o assistente pode errar; custo (mitigado pelo teto diário de 200 perguntas e 10 por minuto, e pelo limite
de gasto na Anthropic); a pergunta é enviada à Anthropic, nos Estados Unidos (aviso na página e no FAQ).

---

## 9. Riscos e plano de saída de cada serviço gratuito

| Serviço | Uso | Risco | Plano de saída |
|---|---|---|---|
| GitHub (repositório, Actions, Releases) | Código, dados, automação | Mudança de política dos planos gratuitos | Tudo é git e arquivos abertos; migra para GitLab ou Codeberg com CI equivalente |
| Cloudflare Pages | Hospedagem do site | Limites (20 mil arquivos, 25 MiB por arquivo) | GitHub Pages já configurado como alternativa automática; qualquer hospedagem de arquivos estáticos serve |
| Cloudflare Worker + D1 | Aprendizado e assistente (opcionais) | Limites do plano gratuito; cobrança se a conta virar paga | O site funciona sem eles; dados são contadores simples exportáveis em SQL |
| Cloudflare Web Analytics | Estatísticas | Descontinuação | Opcional; alternativa livre: GoatCounter ou Plausible auto-hospedado |
| Base dos Dados e geobr (cópias públicas) | Dados de desenvolvimento | Arquivos mudarem ou saírem do ar | O pipeline prefere as fontes oficiais; cada download tem verificação (sha256) registrada |
| Fontes oficiais (IBGE, DATASUS, Ministério das Cidades, FUNAI, BCB) | Dados | Mudança de endereço ou formato | Endereços centralizados em `sources.yaml`; a última versão válida é mantida e marcada |
| OpenFreeMap (mapa de fundo) | Opcional | Fora do ar | O mapa funciona sem mapa de fundo (padrão) |
| unpkg (Decap CMS) | Página de edição | Fora do ar ou adulteração | Integridade verificada (SRI); dá para servir o arquivo do próprio site ou editar direto no GitHub |
| jsDelivr (DuckDB da consulta SQL) | Página `/dados/sql`, só quando a pessoa clica | Fora do ar | Os downloads em CSV e Parquet continuam funcionando; dá para hospedar os arquivos do DuckDB num bucket gratuito (R2) e trocar o endereço em `site/src/pages/dados/sql.astro` |
| APIs do Tesouro (SICONFI), OpenDataSUS e MIDR (CKAN), INEP, ANA Monitor de Secas | Dados | Mudança de endereço ou de formato | Leitores reconhecem colunas pelo nome; falha vira "indisponível" com as colunas vistas no `.meta.json`, sem derrubar o pipeline |
| Anthropic (assistente) | Opcional e pago por uso | Custo | Desligado por padrão, com teto rígido; a camada de provedor permite trocar ou remover |

---

## Onde está cada coisa

- Decisões técnicas: `docs/DECISIONS.md` · Revisões críticas: `docs/REVIEWS/` · Progresso: `docs/PROGRESS.md`
- Metodologia: `docs/METODOLOGIA.md` · Fontes: `docs/DATA_SOURCES.md` · Validação: `docs/VALIDATION_REPORT.md`
- Perguntas em aberto: `docs/QUESTIONS.md` · Especificação original: `docs/SPEC.md`
