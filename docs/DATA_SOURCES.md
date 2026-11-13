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
| SINISA (sucessor do SNIS) | indisponível | Página de resultados do SINISA no gov.br (planilhas e relatórios por tema) | – | PDF/XLSX | Dados públicos | 2023 em diante | A primeira coleta do SINISA (2024, referência 2023) teve 5.241 municípios (94,1%), segundo o release do Ministério das Cidades. Não foi encontrado arquivo aberto estável por município. Ver METODOLOGIA, "Transição SNIS → SINISA". |
| DATASUS SIH/SUS (RD) | **só oficial** | `ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/RD{UF}{AA}{MM}.dbc` | nenhum alcançável (o espelho S3 de terceiros e o espelho Parquet do pacote healthbR estão bloqueados ou exigem credencial) | DBC | Dados públicos MS | últimos 5 anos completos | Leitura por residência exige ler as 27 UFs (`residence_scope: all_ufs`). Extratos DRSAI ficam em cache entre execuções. |

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
| P1 | DATASUS SIM (óbitos por causa) | indisponível | FTP DATASUS (DO{UF}{AAAA}.dbc) | BD tem só óbitos totais por município, sem causa | O componente "óbitos evitáveis" da calculadora fica desligado e marcado "sem dado". |
| P1 | SISAGUA | indisponível | OpenDataSUS / dados.gov.br | não encontrado | Dimensão "qualidade da água" do índice fica sem dado (é reponderada). |
| P1 | S2ID (decretos) | indisponível | Dados abertos do MIDR | não encontrado | Dimensão "risco climático" usa só o Semiárido como contexto (sem pontuação) até o S2ID entrar. |
| P1 | FUNAI terras indígenas | espelho | GeoServer WFS da FUNAI | geobr v2.0.0 `indigenouslands_2024` (FUNAI, 2024) | 28 TIs tocam a BA. Fase oficial (declarada, homologada, regularizada etc.) exibida. |
| P1 | INCRA territórios quilombolas | indisponível | Acervo fundiário do INCRA | geobr: nome do arquivo não encontrado no release | Contagem de pessoas quilombolas por município (Censo) é exibida no lugar dos polígonos. |
| P1 | Fundação Cultural Palmares | indisponível | Site da Palmares (lista de certidões) | não encontrado | – |
| P1 | Censo 2022: quilombolas | espelho | SIDRA 9578 (citada pelo IBGE) | BD `populacao_grupo_idade_sexo_quilombola` | Soma de células por idade e sexo: células sob sigilo vêm vazias, então o total é um **mínimo** (BA: 392.439 no espelho). Rotulado na interface. |
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
