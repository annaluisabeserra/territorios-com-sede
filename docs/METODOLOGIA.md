# Metodologia

Como cada número da plataforma é calculado, de onde vem e quais são seus limites. A lista de indicadores, com
fórmula, fonte e limitações, é gerada de `pipeline/config/indicadores.yaml` (fonte única da verdade) e aparece no
site em `/metodologia`. Este documento explica as regras gerais e as escolhas metodológicas.

## Princípios

1. **Nenhum número sem fonte.** Cada valor vem de uma base pública identificada, com período de referência, URL e
   data de coleta (arquivo `.meta.json` de cada base).
2. **Ausência não é zero.** Dado indisponível aparece como "sem dado". Valores ausentes nunca entram em médias,
   rankings ou somas como zero.
3. **Estimativa é rotulada.** Projeções (termômetro) e cálculos de economia (calculadora) aparecem como
   estimativas, com premissas e faixa de sensibilidade visíveis.
4. **Médias escondem territórios.** Sempre que possível mostramos o município, os vizinhos, a mediana da UF e a do
   Brasil, e a situação de povos e comunidades tradicionais.

## Chaves e recortes

- Unidade de análise: município, identificado pelo código IBGE de 7 dígitos. O DATASUS usa 6 dígitos (sem o dígito
  verificador); a conversão usa uma tabela de-para construída a partir da lista oficial e validada (cobertura de
  100% dos códigos do SIH, exceto os códigos "município ignorado", terminados em 0000, que são contados e reportados).
- Tudo é parametrizado por UF (`pipeline/config/ufs.yaml`).

## Fontes e transição SNIS → SINISA

- **SNIS** (Sistema Nacional de Informações sobre Saneamento): dados autodeclarados pelos prestadores, série
  1995–2022 (ano de referência). A partir do ano de referência 2023, o Ministério das Cidades substituiu o SNIS pelo
  **SINISA** (Sistema Nacional de Informações em Saneamento Básico), com primeira coleta em 2024 e 5.241 municípios
  participantes. O SINISA muda conceitos, formulários e denominadores. Enquanto não houver arquivo aberto e estável
  por município, a série da plataforma termina em 2022, e o `.meta.json` registra isso.
- **Quebra de série dentro do SNIS:** o ano de referência 2022 usa a população do Censo 2022 como denominador; os
  anos anteriores usavam estimativas populacionais. Isso pode gerar um degrau em 2022. Quando o SINISA for integrado,
  a série terá um campo de metodologia e a regressão do termômetro não atravessará a quebra (backlog).
- **Valores fora da faixa:** coberturas entre 100% e 105% (diferença de denominador) são limitadas a 100%; acima de
  105%, e perdas fora de 0–100%, são tratadas como erro de declaração (sem dado). As contagens ficam nos metadados.
- **Desatualização:** um valor do SNIS com mais de 2 anos de defasagem em relação ao último ano disponível na UF é
  exibido como "último dado: AAAA", mas não entra no índice, nas medianas nem nas sugestões.
- **Censo 2022 × SNIS:** o Censo pergunta ao morador como a casa é abastecida e para onde vai o esgoto; o SNIS
  informa quanto da população o prestador declara atender. Quando os dois divergem em mais de 15 pontos percentuais,
  a ficha mostra os dois e explica. A comparação de esgoto usa a categoria do Censo mais próxima do conceito do SNIS
  (rede geral ou pluvial), não o "esgoto adequado" (que inclui fossa séptica).

## Termômetro 2033 {#termometro}

A Lei 14.026/2020 (Marco Legal do Saneamento) fixa para 31/12/2033: 99% da população com água potável e 90% com
coleta e tratamento de esgoto.

- **Água:** atendimento total de água (SNIS IN055). Mede atendimento pela rede, não potabilidade nem regularidade.
- **Esgoto:** esgoto coletado **e tratado**, estimado por IN056 × IN016 ÷ 100 (atendimento por rede coletora ×
  tratamento do esgoto coletado). Usar só o IN056 superestimaria o progresso: na BA, 26 dos 39 municípios que
  pareceriam "no ritmo" tinham tratamento zero.
- **Tendência:** regressão linear (mínimos quadrados) sobre os anos disponíveis numa janela de 8 anos terminando
  no último ano do SNIS na UF, com no mínimo 3 pontos. O último ponto do município precisa estar entre os 2 anos
  mais recentes.
- **Classificação:** *meta atingida* (dois anos consecutivos acima da meta); *no ritmo* (ano projetado ≤ 2033);
  *atrasado* (projeção depois de 2033, ou tendência parada ou caindo); *sem dados suficientes*.
- **Incerteza:** a faixa de anos usa o intervalo de confiança de 95% da inclinação. Se o intervalo inclui
  estagnação, a projeção é marcada como incerta. A projeção é linear e indicativa: ela não prevê obras, apenas
  mostra para onde a tendência recente leva.

## Doenças relacionadas ao saneamento ambiental inadequado (DRSAI) {#drsai}

Base: classificação da Funasa (2010), derivada de Cairncross & Feachem (1993) e Mara & Feachem (1999).
Configuração em `pipeline/config/cid_drsai.yaml`.

- **Núcleo conservador (padrão):** transmissão feco-oral (A00–A09, B15), contato com a água (A27, B65) e
  geo-helmintos e teníases (B68–B69, B76–B83).
- **Camada opcional "vetores":** dengue (A90–A91 e A97), chikungunya e zika (A92), febre amarela (A95), malária
  (B50–B54), leishmanioses (B55), doença de Chagas (B57), filariose (B74). A relação com o saneamento é mais
  indireta (água parada, drenagem, lixo). A codificação de dengue mudou com a revisão da CID-10 (A97), por isso os
  dois conjuntos de códigos estão na lista.
- **Fora da lista, por decisão conservadora:** a categoria "relacionadas à higiene" da Funasa (tracoma A71,
  conjuntivites H10, micoses superficiais B35–B36), porque a internação por essas causas é rara e a atribuição ao
  saneamento é menos direta. Pendência de confirmação na publicação original: Q4 em `QUESTIONS.md`.

## Internações e custo SUS

- Fonte: SIH/SUS, arquivos RD (AIH reduzida), por **município de residência** do paciente. Como os arquivos são
  organizados pela UF do hospital, o pipeline lê as 27 UFs para captar moradores internados em outros estados.
- **Internação:** AIH do tipo 1 (`IDENT == 1`). AIHs de longa permanência (tipo 5) não contam como nova internação,
  mas o valor delas entra no custo.
- **Valor:** `VAL_TOT`, valor pago pela tabela SUS (abaixo do custo econômico real), corrigido **mês a mês** pelo
  IPCA para reais da média do ano-base. Se faltar IPCA para algum mês do período, o valor fica indisponível.
- **Período:** média dos últimos 5 anos completos, por ano de processamento (padrão do TabNet). Anos sem internação
  num município contam como zero (o arquivo existe; não houve AIH).
- **Privacidade:** médias anuais de óbitos menores que 5 são publicadas como "menos de 5". Os extratos intermediários
  são agregados por faixa etária e nunca guardam registros individuais.

## Calculadora de economia / SROI {#calculadora}

Mostra quanto o território economizaria reduzindo as DRSAI em X%. **Não estima o custo de obras.**

- **Benefício anual base (B):** soma dos componentes ligados.
  - Custo hospitalar SUS: média anual corrigida do valor pago.
  - Produtividade perdida: dias de internação × renda diária de referência (rendimento domiciliar per capita do
    Censo ÷ 30). Para pacientes menores de 14 anos, o dia conta como um dia de adulto acompanhante.
  - Dias letivos perdidos: dias de internação de pacientes de 6 a 17 anos (indicador, não monetizado).
  - Atendimento ambulatorial e óbitos evitáveis: desligados (sem referência documentada ou sem dado).
- **Economia anual:** B × redução.
- **Valor presente:** VP = Σ (t = 1..H) B × r / (1 + taxa)^t, com taxa social de desconto de 8,5% ao ano.
- **SROI (opcional):** VP = Σ B × r × (1 − deadweight) × atribuição × (1 − drop-off)^(t−1) / (1 + taxa)^t;
  SROI = VP ÷ investimento. Padrões: deadweight 10%, atribuição 80%, drop-off 5% ao ano (ADR-010), seguindo os
  princípios da Social Value International.
- **Sensibilidade:** mínimo e máximo do VP variando a taxa de desconto (4% a 12%) e, no modo SROI, deadweight,
  atribuição e drop-off nas faixas documentadas.
- **Cenário SDW 92%:** dado informado pela SDW, em validação independente (Q6).
- **Paridade:** a mesma conta roda em Python (pipeline) e em TypeScript (site), com igualdade exata verificada em
  204 casos.

## Índice de prioridade territorial

- Cinco dimensões com pesos padrão: déficit de acesso (30%), carga de saúde (25%), vulnerabilidade social (20%),
  risco climático e hídrico (15%), qualidade da água (10%). Configuração: `pipeline/config/pesos_indice.yaml`.
- Cada componente vira percentil dentro da UF (0 = melhor situação, 100 = pior), com empates pela média dos postos.
- Dimensão = média dos componentes presentes. Índice = média ponderada das dimensões presentes, com os pesos
  renormalizados. **Nada é imputado como zero.**
- Município com menos de 3 dimensões fica sem posição no ranking. Se a UF inteira não tem 3 dimensões, o índice
  não é publicado (situação da versão atual: faltam saúde, clima e qualidade da água).
- Fallback declarado: se o Censo não estiver disponível para a UF, o déficit de acesso usa o SNIS (sinalizado).
- Pesos ajustáveis pelo usuário no site; análise de sensibilidade (±10 p.p. por peso, top 20) publicada.

## Agir: tecnologias sociais sugeridas {#agir}

Regras simples, sem estimativa de custo (`pipeline/transform/act.py`):

| Solução | Dispara quando |
|---|---|
| Captação de água da chuva e cisternas | Município no Semiárido ou com decretos de seca nos últimos 5 anos |
| Filtros e tratamento no ponto de uso | ≥ 20% da população fora da rede de água ou > 10% de amostras fora do padrão |
| Unidades autônomas com energia solar | ≥ 30% da população fora da rede de água (energia não avaliada) |
| Saneamento descentralizado | Esgoto adequado < 50% (Censo), rede coletora < 50% (SNIS) ou nenhum prestador de esgoto declarado |
| Redução de perdas | Perdas ≥ 40% e população ≥ 50 mil |
| Educação ambiental | Sempre |

## Povos e comunidades tradicionais

Só polígonos oficiais já públicos (terras indígenas da FUNAI) e contagens agregadas por município (Censo 2022).
Nunca a localização de aldeias, casas ou povos isolados. Status oficial com fonte. Detalhes na página
`/povos-e-comunidades` e na seção 7 da SPEC.
