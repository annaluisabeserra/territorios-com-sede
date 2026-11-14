# Fontes de dados

Status de cada fonte (SPEC §5), verificado em 13/11/2026. URLs completas em `pipeline/config/sources.yaml`.

**Contexto da verificação:** a plataforma foi construída num ambiente cuja política de rede bloqueia os
domínios do governo (`*.ibge.gov.br`, `ftp.datasus.gov.br`, `*.gov.br`, `dados.gov.br`, `api.bcb.gov.br`).
Por isso cada fonte tem uma cadeia de URLs: a oficial primeiro e, quando existe, um espelho público
rastreável. O `.meta.json` de cada arquivo registra qual URL foi usada (ADR-002). No GitHub Actions, que tem
rede aberta, a URL oficial é tentada primeiro.

Legenda: **ok** (oficial em uso) · **espelho** (em uso a partir de cópia pública do dado oficial) ·
**só oficial** (implementado, aguarda execução com rede aberta) · **indisponível** (motivo registrado).

## P0

| Fonte | Status no build atual | Oficial (verificar com rede) | Espelho usado | Formato | Licença | Referência | Observações |
|---|---|---|---|---|---|---|---|
| IBGE Localidades | espelho | `servicodados.ibge.gov.br/api/v1/localidades/estados/{UF}/municipios` | Base dos Dados `br_bd_diretorios_brasil.municipio` (GCS público, atualizado em 12/12/2023) | JSON / CSV | Dados públicos IBGE; BD CC BY 4.0 | vigente | BA = **417** municípios e CE = **184**, conferidos no espelho e no geobr. |
| IBGE Malhas | espelho | API de malhas v3 (`/api/v3/malhas/estados/{UF}?intrarregiao=municipio`) | geobr v2.0.0 (Ipea), `municipalities_2022_simplified.parquet`, release no GitHub | GeoJSON / GeoParquet | Dados públicos IBGE; geobr MIT | 2022 | Simplificada; o site simplifica de novo para a web. |
| Censo 2022: população | espelho | API SIDRA v3 com descoberta por catálogo (o pipeline acha a tabela pelo nome) | BD `br_ibge_censo_2022.populacao_idade_sexo` (da tabela SIDRA 9514) | CSV | Dados públicos IBGE | 01/08/2022 | Soma confere com o total oficial: BA **14.141.626**; CE **8.794.957**. |
| Censo 2022: água (forma de abastecimento) | **só oficial** | SIDRA v3 (descoberta: agregado do Censo com "abastecimento de água", variável de moradores, município) | nenhum encontrado | JSON | Dados públicos IBGE | 01/08/2022 | Fontes secundárias citam as tabelas 6803, 6804 e 6909 sem consenso, por isso a escolha da tabela é automática e registrada no `.meta.json`. |
| Censo 2022: esgotamento sanitário | **só oficial** | SIDRA v3 (descoberta: "esgotamento sanitário") | nenhum encontrado | JSON | Dados públicos IBGE | 01/08/2022 | Esgoto adequado = rede geral/pluvial/fossa ligada à rede + fossa séptica não ligada (critério Plansab). |
| Censo 2022: destino do lixo | espelho | SIDRA | BD `caracteristica_domicilio_grupo_idade_raca_destino_lixo` | CSV | Dados públicos IBGE | 01/08/2022 | A tabela traz o subtotal "Coletado" junto das partes: o pipeline exclui as partes para não contar em dobro. |
| SNIS série histórica | espelho | `app4.cidades.gov.br/serieHistorica` (consulta interativa, sem API estável) | BD `br_mdr_snis.municipio_agua_esgoto` (1995–2022, atualizado em 03/07/2024) | CSV | Dados públicos | 1995–2022 | Mapeamento dos códigos na tabela abaixo. 409 dos 417 municípios da BA responderam em 2022. |
| SINISA (sucessor do SNIS) | **só oficial** (leitor pronto, roda no GitHub Actions) | Páginas de resultados por edição: `gov.br/cidades/.../sinisa/resultados-sinisa/resultados-sinisa-{2024,2025,2026}` | – | XLSX/CSV/ZIP | Dados públicos | 2023 em diante | Primeira coleta (2024, ref. 2023): 5.241 municípios. Na coleta 2024, 5.144 responderam água e 3.903 esgoto. Códigos: IAG0001 = IN055, IES0001 = IN056, IES2003 = IN046 (Trata Brasil/GO Associados, "Estudo sobre as alterações metodológicas do SINISA", 2025; Ranking ABES 2025). Ver ADR-012. |
| DATASUS SIH/SUS (RD) | **só oficial** | `ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/RD{UF}{AA}{MM}.dbc` | nenhum alcançável (o espelho S3 de terceiros e o espelho Parquet do pacote healthbR estão bloqueados ou exigem credencial) | DBC | Dados públicos MS | últimos 5 anos completos | Leitura por residência exige ler as 27 UFs (`residence_scope: all_ufs`). Extratos DRSAI ficam em cache entre execuções. |
| DATASUS SIM (DO) | **só oficial** | `ftp://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DORES/DO{UF}{AAAA}.dbc` | nenhum (BD `br_ms_sim.municipio` só tem total de óbitos, sem causa) | DBC | Dados públicos MS | últimos 5 anos consolidados | Causa básica (CAUSABAS), mesmos grupos de CID do SIH. ADR-014. |
| SISAGUA, controle mensal (parâmetros básicos) | **só oficial** | CKAN do OpenDataSUS, conjunto `sisagua-controle-mensal-parametros-basicos` (um CSV por ano) | – | CSV | Dados públicos MS | último ano completo | Colunas reconhecidas pelo nome. O portal dados.gov.br avisou em 2026 que links do SISAGUA estavam fora do ar; o OpenDataSUS é a fonte usada. |
| S2ID, reconhecimentos federais | **só oficial** | CKAN do portal de dados abertos do MIDR, conjunto `s2id_sedec` (exportação mensal) | – | CSV/XLSX | Dados públicos MIDR | últimos 5 anos completos | Seca/estiagem e chuvas pelo texto do tipo ou código COBRADE. |
| Monitor de Secas (ANA) | **só oficial** | `monitordesecas.ana.gov.br/dados-sig?ano={AAAA}` (shapefile mensal em .zip) | – | SHP | Dados públicos ANA | últimos 12 mapas | Classe S0–S4 no ponto representativo do município. |
| Censo Escolar (INEP) | **só oficial** | `download.inep.gov.br/dados_abertos/microdados_censo_escolar_{AAAA}.zip` | – | CSV em ZIP | Dados públicos INEP | ano mais recente publicado | Tabela de escolas; só públicas em atividade. |
| SICONFI, DCA Anexo I-E | **só oficial** | `apidatalake.tesouro.gov.br/ords/siconfi/tt/dca` (uma consulta por município) | BD só tem nível UF | JSON | Dados públicos Tesouro | último exercício declarado | Função 17 (Saneamento), despesa liquidada. |

### Mapeamento SNIS → colunas do espelho

| Código SNIS | Indicador | Coluna (Base dos Dados) | Nome interno |
|---|---|---|---|
| IN055 | Atendimento total de água | `indice_atendimento_total_agua` | `snis_agua_pct` |
| IN056 | Atendimento total de esgoto (ref. municípios atendidos com água) | `indice_atendimento_esgoto_agua` | `snis_esgoto_pct` |
| IN046 | Esgoto tratado ref. à água consumida | `indice_esgotamento_agua_consumida` | `snis_tratamento_pct` |
| IN049 | Perdas na distribuição | `indice_perda_distribuicao_agua` | `snis_perdas_pct` |
| IN015 | Coleta de esgoto | `indice_coleta_esgoto` | `snis_coleta_esgoto_pct` |
| IN016 | Tratamento de esgoto (ref. ao coletado) | `indice_tratamento_esgoto` | `snis_tratamento_coletado_pct` |
| IN022 | Consumo médio per capita de água | `indice_consumo_agua_per_capita` | `snis_consumo_lhabdia` |

O mapeamento segue os nomes do glossário do SNIS. Uma conferência numérica (IN055 ≈ população atendida ÷
população estimada) está no `VALIDATION_REPORT.md`.

## P1 e P2

| Prioridade | Fonte | Status | Oficial | Espelho / alternativa | Observações |
|---|---|---|---|---|---|
| P1 | DATASUS SIM (óbitos por causa) | só oficial (ADR-014) | FTP DATASUS (DO{UF}{AAAA}.dbc) | BD tem só óbitos totais por município, sem causa | Leitor pronto; ver tabela P0. |
| P1 | SISAGUA | só oficial (ADR-014) | OpenDataSUS (CKAN) | não encontrado | Leitor pronto; alimenta a dimensão "qualidade da água". |
| P1 | S2ID (decretos) | só oficial (ADR-014) | Dados abertos do MIDR (CKAN) | não encontrado | Leitor pronto; alimenta a dimensão "risco climático" com o Monitor de Secas. |
| P1 | FUNAI terras indígenas | espelho | GeoServer WFS da FUNAI | geobr v2.0.0 `indigenouslands_2024` (FUNAI, 2024) | 28 TIs tocam a BA. Fase oficial (declarada, homologada, regularizada etc.) exibida. |
| P1 | INCRA territórios quilombolas | indisponível | Acervo fundiário do INCRA (`certificacao.incra.gov.br`, camada de áreas quilombolas); registrado em `sources.yaml` | geobr: nome do arquivo não encontrado no release | Sem status oficial de titulação na plataforma até a fonte entrar. A ficha diz isso explicitamente. |
| P1 | Fundação Cultural Palmares | indisponível | Página de certificação quilombola da FCP (planilha sem endereço estável); registrado em `sources.yaml` | não encontrado | Sem lista de comunidades certificadas até a fonte entrar. |
| P1 | Censo 2022: quilombolas | espelho | SIDRA 9578 (citada pelo IBGE) | BD `populacao_grupo_idade_sexo_quilombola` | Soma de células por idade e sexo: células sob sigilo vêm vazias, então o total é um **mínimo**. Na UF o desvio é pequeno (BA: 392.439 no espelho), mas no município pode ser grande (mediana de 51 de 84 células sob sigilo). Município com todas as células sob sigilo fica sem dado. A ficha mostra a fração de células sob sigilo. Rotulado na interface. |
| P1 | Censo 2022: indígenas | espelho (parcial) | SIDRA (pessoas indígenas) | BD `populacao_grupo_idade_sexo_raca` (cor ou raça indígena) | "Cor ou raça indígena" é menor que "pessoas indígenas" do IBGE (que inclui quem se declara indígena em TIs). Rotulado com o nome exato. |
| P2 | Semiárido (SUDENE) | espelho | Sudene | geobr v2.0.0 `semiarid_2022` | 287 municípios da BA. Usado como filtro e nas regras de "Agir". |
| P2 | ANA Atlas Esgotos | espelho | ANA / SNIRH | BD `br_ana_atlas_esgotos.municipio` | Referência 2013, população urbana. Usado como contexto de tratamento. |
| P2 | IPCA | espelho | BCB SGS 433 | BD `br_ibge_ipca.mes_brasil` (até 07/2024) | Ano-base dos valores = último ano completo disponível. |
| P2 | ICMBio (RESEX/RDS) | indisponível | Dados geoespaciais ICMBio/MMA | BD `br_geobr_mapas.unidade_conservacao` existe (WKT) mas não foi integrado | Backlog. |
| P2 | CadÚnico | indisponível | VIS Data / MDS | não encontrado | Componente de vulnerabilidade reponderado. |
| P2 | SICONFI | indisponível | API do Tesouro | BD só tem nível UF | Backlog. |
| P2 | Renda (Censo 2022) | indisponível | SIDRA | não encontrado | O componente de produtividade da calculadora fica "sem dado" até a fonte entrar. |
| – | Mapa base | indisponível neste ambiente | OpenFreeMap (sem chave) | – | O mapa funciona sem mapa base (polígonos sobre fundo neutro); o mapa base é opcional (ADR-004). |

## Divergência entre fontes

SNIS (autodeclarado pelos prestadores) × Censo (medida domiciliar): quando ambos existirem e a diferença
passar de 15 pontos percentuais, a ficha mostra os dois com explicação. Configurável em `indicadores.yaml`.

## Atribuição e licenças dos espelhos

- **Base dos Dados** (basedosdados.org): dados tratados sob CC BY 4.0; os valores são do IBGE, do Ministério das Cidades e da ANA (dados públicos). Três arquivos têm o sufixo `_bdpro` e estão no bucket público; ver Q3 em `QUESTIONS.md`. Citação: *Base dos Dados. Repositório de dados abertos. basedosdados.org.*
- **geobr** (Ipea): código MIT; dados do IBGE, da Sudene e da FUNAI. Citação: *Pereira, R.H.M.; Gonçalves, C.N. et al. geobr: Loads Shapefiles of Official Spatial Data Sets of Brazil. Ipea.*
- Os espelhos são arquivos mutáveis sem versão. O sha256 de cada download fica no `.meta.json`, e o histórico do git mostra quando um valor mudou.
