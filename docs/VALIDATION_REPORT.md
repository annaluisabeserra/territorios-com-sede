# Relatório de validação

Gerado em 13/11/2026 19:59 UTC por `pipeline/validate/report.py`. Regenerado a cada execução do pipeline.

Este relatório complementa as checagens automáticas (que derrubam o pipeline) com checagens de plausibilidade que exigem leitura humana. Itens marcados **pendente** dependem de fontes que não puderam ser lidas no ambiente de construção (ver `docs/DATA_SOURCES.md`).

## Calculadora

- Casos calculados à mão: `pipeline/tests/test_calculator.py` (VP de 3 anos a 10% = R$ 186.513,90; SROI 1,281).
- Propriedades testadas com Hypothesis: monotonicidade na redução, VP zero com 0%, convergência para a soma simples quando a taxa vai a zero, VP decrescente na taxa.
- Paridade Python × TypeScript: 204 casos com igualdade exata (`===`), incluindo a faixa de sensibilidade.

## Bahia (BA)

### 1. Origem de cada base

| Etapa | Status | Origem | Período | Observação |
|---|---|---|---|---|
| ana_atlas | ok | espelho | 2013 (população urbana) |  |
| censo_agua | unavailable | – | – | FetchError: todas as URLs falharam: |
| censo_esgoto | unavailable | – | – | FetchError: todas as URLs falharam: |
| censo_lixo | ok | espelho | 2022 (data de referência 01/08/2022) |  |
| censo_quilombola | ok | espelho | 2022 (data de referência 01/08/2022) | {"lower_bound": true} |
| censo_raca | ok | espelho | 2022 (data de referência 01/08/2022) |  |
| ipca | stale | espelho | até 07/2024 | {"stale": true, "stale_months": 28} |
| malhas | ok | espelho | 2022 |  |
| municipios | ok | espelho | vigente |  |
| populacao | ok | espelho | 2022 (data de referência 01/08/2022) |  |
| semiarido | ok | espelho | 2022 |  |
| sih_drsai | unavailable | – | – | ImportError: cannot import name 'read_dbc' from 'pyreaddbc' (/home/user/territorios-com-sede/.venv/lib/python3.13/site-p |
| snis | ok | espelho | 1995–2022 | {"snis_perdas_pct_invalid_to_null": 60, "snis_agua_pct_capped": 0, "snis_agua_pct_absurd_to_null": 0, "snis_coleta_esgot |
| terras_indigenas | ok | espelho | vigente na data de coleta |  |

### 2. Checagens automáticas (SPEC §9)

- Erros: **0** (o pipeline falha se houver algum).
- Municípios: 417 (esperado 417).
- População somada: 14.141.626 (oficial 14.141.626).
- Aviso: 75 saltos > 50% ao ano nas séries SNIS (últimos 8 anos)

Maiores saltos anuais nas séries do SNIS (aviso, não erro; em geral mudança de declaração do prestador):

| Município | Indicador | Ano | Variação relativa ao ano |
|---|---|---|---|
| Novo Horizonte | snis_agua_pct | 2017 | 2.712% |
| São Sebastião do Passé | snis_esgoto_pct | 2016 | 2.442% |
| Araci | snis_esgoto_pct | 2016 | 1.910% |
| Itiúba | snis_esgoto_pct | 2022 | 1.029% |
| Senhor do Bonfim | snis_esgoto_pct | 2022 | 936% |
| Senhor do Bonfim | snis_esgoto_pct | 2020 | 561% |
| Mairi | snis_esgoto_pct | 2022 | 560% |
| Urandi | snis_agua_pct | 2021 | 247% |
| Santo Estêvão | snis_esgoto_pct | 2016 | 242% |
| Sítio do Quinto | snis_esgoto_pct | 2020 | 242% |

### 3. Internações (SIH) × TabNet

**Pendente.** O SIH não pôde ser lido no ambiente de construção (FTP do DATASUS bloqueado). Quando o pipeline rodar no GitHub Actions, conferir para a amostra abaixo:

- TabNet → Epidemiológicas e Morbidade → Morbidade Hospitalar do SUS (SIH/SUS) → Geral, por local de residência (a partir de 2008) → UF.
- Linha: Município; Coluna: Ano processamento; Conteúdo: Internações e Valor total; Seleções: Lista Morb CID-10 com os capítulos correspondentes às categorias DRSAI do núcleo (ou, mais preciso, comparar contra o próprio .dbc filtrado).
- Amostra: Salvador, Feira de Santana, Vitória da Conquista, Juazeiro, Ilhéus; Ceará: São Gonçalo do Amarante, Fortaleza.
- Diferenças esperadas: o TabNet agrega por lista de morbidade (grupos de CID), não por categoria de 3 caracteres; AIHs de longa permanência (IDENT 5) não contam como internação.


### 4. Cobertura SNIS × Censo

**Pendente**: o Censo 2022 de água e esgoto (SIDRA) não pôde ser lido no ambiente de construção. A ficha e este relatório passam a mostrar os maiores divergentes (limiar de 15 p.p.) assim que a fonte entrar.


Consistência interna do SNIS (IN055 × população atendida ÷ população do Censo, 2022): diferença mediana ≈ 0 p.p., desvio de 0,24 p.p. (conferido na revisão do M2).

### 5. Municípios sem dado, por indicador

| Indicador | Com dado | Sem dado | Exemplos sem dado |
|---|---|---|---|
| snis_agua_pct | 413 | 4 | Barro Preto, Coribe, Pilão Arcado, Sítio do Mato |
| snis_esgoto_pct | 216 | 201 | Acajutiba, Água Fria, Érico Cardoso, Alcobaça, Almadina |
| snis_esgoto_tratado_pct | 216 | 201 | Acajutiba, Água Fria, Érico Cardoso, Alcobaça, Almadina |
| snis_perdas_pct | 413 | 4 | Barro Preto, Coribe, Pilão Arcado, Sítio do Mato |
| censo_lixo_coletado_pct | 417 | 0 |  |
| pop_quilombola | 305 | 112 | Aiquara, Almadina, Andorinha, Anguera, Apuarema |
| drsai_internacoes | 0 | 417 | fonte indisponível |
| censo_agua_rede_pct | 0 | 417 | fonte indisponível |

### 6. Termômetro 2033

- Água (IN055, meta 99%): atrasado: 336; no_ritmo: 56; atingida: 15; sem_dados: 10
- Esgoto coletado e tratado (IN056 × IN016, meta 90%): sem_dados: 237; atrasado: 170; no_ritmo: 10

### 7. Índice de prioridade: revisão do topo e da base

O índice oficial não ranqueia nesta versão: há 2 de 5 dimensões (acesso, vulnerabilidade), abaixo do mínimo de 3. Para testar o mecanismo, abaixo está um **ranking exploratório** com as dimensões disponíveis (não publicado no site):

| Posição | Município | Nota exploratória | Sem água (SNIS) | Sem esgoto (SNIS) | % quilombola + indígena |
|---|---|---|---|---|---|
| 1 | Maraú | 99 | 81,4 | sem dado | 31,1 |
| 2 | Caetanos | 98 | 75,9 | sem dado | sem dado |
| 3 | Baianópolis | 97 | 73,1 | sem dado | sem dado |
| 4 | Brejolândia | 97 | 72,8 | sem dado | sem dado |
| 5 | Guajeru | 96 | 72,4 | sem dado | sem dado |
| 6 | São Miguel das Matas | 93 | 67,8 | sem dado | sem dado |
| 7 | Jucuruçu | 93 | 67,7 | sem dado | sem dado |
| 8 | Banzaê | 93 | 65,8 | 93,0 | 29,1 |
| 9 | Oliveira dos Brejinhos | 93 | 67,4 | sem dado | sem dado |
| 10 | Muquém de São Francisco | 92 | 57,3 | 94,2 | 25,7 |
| 406 | Barrocas | 10 | 0,0 | sem dado | 0,7 |
| 407 | Macarani | 9 | 11,2 | 11,2 | 0,1 |
| 408 | Ibicaraí | 9 | 2,8 | sem dado | sem dado |
| 409 | Dom Macedo Costa | 5 | 0,2 | sem dado | sem dado |
| 410 | Feira da Mata | 5 | 0,2 | sem dado | sem dado |
| 411 | Valente | 4 | 0,2 | sem dado | 0,1 |
| 412 | Itapetinga | 2 | 0,0 | 2,9 | sem dado |
| 413 | Tanquinho | 1 | 0,0 | sem dado | 0,1 |
| 414 | Itajuípe | 0 | 0,0 | 0,0 | sem dado |
| 415 | Saubara | 0 | 0,0 | sem dado | 0,0 |

**Leitura (revisão manual):** o topo exploratório é dominado pela falta de rede de água (57% a 81% da população fora da rede); onde há dado de povos tradicionais (Maraú, Banzaê, Muquém de São Francisco) ele reforça a posição. A base reúne municípios com rede de água quase universal. O mecanismo responde na direção esperada. Ressalvas: (1) sem saúde, clima e qualidade da água, este ranking não serve para priorizar; (2) o percentual quilombola + indígena fica sem dado onde o espelho do Censo tem sigilo total, então a dimensão vulnerabilidade pesa pouco até a tabela oficial do SIDRA entrar; (3) o esgoto do SNIS falta em muitos municípios pequenos (provável ausência de rede), o que os favorece; o Censo corrige isso.

Análise de sensibilidade (±10 p.p. por peso, top 20): status `sem_ranking`.

## Ceará

Sem dados processados.

