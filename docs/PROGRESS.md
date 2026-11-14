# Progresso

Registro por marco (SPEC §10). Revisões críticas em `docs/REVIEWS/`.

| Marco | Situação | Critério de aceite | Observação |
|---|---|---|---|
| M0 Fundação | ✅ | `make test` e `make lint` passam | CI configurado; ficará verde no primeiro push (não há repositório remoto no ambiente de construção) |
| M1 Investigação de fontes | ✅ | Fontes P0 acessíveis ou com alternativa documentada | Rede do ambiente bloqueava o governo: cadeia oficial → espelho (ADR-002); SIH e Censo água/esgoto ficam para o GitHub Actions |
| M2 Pipeline P0 (BA) | ✅ | Checagens da §9 passam; Parquet e JSON gerados | Revisão M2 com 4 personas, todos os graves corrigidos |
| M3 Indicadores e cálculos | ✅ | Testes unitários e de propriedade; VALIDATION_REPORT | Relatório gerado automaticamente; seções do SIH e SNIS × Censo pendentes da fonte |
| M4 Site núcleo | ✅ | Playwright cobre fluxos; axe sem violações graves | 54 testes e2e (desktop e celular), 15 páginas com axe; Lighthouse ≥ 90 |
| M5 Calculadora TS e perguntas | ✅ | Paridade exata; links compartilháveis | 248 casos de paridade da calculadora e 151 do índice, comparados no CI |
| M6 Camadas P1/P2 e comunidades | ✅ | Regras da §7; camadas indisponíveis documentadas | FUNAI, RESEX/RDS, Semiárido, ANA integrados; 8 fontes registradas como indisponíveis com motivo; lista de retiradas |
| M7 Conteúdo e extras | ✅ | Build completo sem erros; Lighthouse ≥ 90 | FAQ 24, escola, dados abertos, 601 cards, CMS, Worker, assistente desligado, workflows |
| M8 Escala e endurecimento | ✅ | CE sem alteração de código; HANDOFF | CE rodou sem mudança específica de UF; um defeito genérico de escala foi corrigido (ver REVIEWS/M8.md) |

## Números da entrega

- 601 fichas de município (417 BA + 184 CE), 1.219 páginas estáticas, 601 cards de compartilhamento.
- Testes: 77 (pipeline) + 416 (Vitest) + 54 (Playwright/axe) + teste de privacidade do Worker.
- Ficha: 0 KB de JavaScript, ~8 KB comprimida; mapa interativo carregado sob demanda.

## Backlog (itens não graves das revisões)

- Link direto à fonte oficial ao lado do espelho (o `.meta.json` já registra a tabela oficial quando ela roda).
- Total oficial de pessoas indígenas e de quilombolas (SIDRA) substituindo as somas do espelho (entra no Actions).
- Comparação do saneamento de domicílios quilombolas e indígenas com o município (Censo 2022).
- Etnia das terras indígenas pelo campo oficial da FUNAI (entra no Actions).
- Uso da ANA como reforço do componente de esgoto no índice; parâmetro de defasagem na calculadora; Theil–Sen como alternativa robusta no termômetro.
- Campo de metodologia na série (quebra SNIS 2022 e transição para o SINISA).
- Leitores de SISAGUA, S2ID, INCRA, Palmares, CadÚnico e SICONFI.
- Formulário de retirada sem login (hoje: e-mail e formulário do GitHub).
- Ações do GitHub fixadas por SHA (exige acesso à API do GitHub).
- Testar a publicação de ponta a ponta (Cloudflare) com as ações já atualizadas para Node 24 e o runner fixado em ubuntu-24.04; migrar para o Ubuntu 26 depois de um teste do CI nele.

### Resolvidos depois da entrega inicial

- Rótulos da calculadora em linguagem simples (termo técnico entre aspas, como apoio); barras do índice explicadas sem "percentil".
- Fonte de cada célula da ficha com ano e código do SNIS (ex.: "SNIS 2022, IN055").
- Rótulos do gráfico legíveis no celular (~12 px), sem cortes nas bordas.
- `aria-label` próprio em cada tabela e em cada formulário de busca.
- Cabeçalho deixa de ficar preso no topo no celular (libera ~120 px de tela).
- Página da escola com lista de todos os municípios (funciona sem JavaScript).
- Worker: lista de origens permitidas (domínio próprio + plano B) e eventos aceitos só do próprio site.
- Pipeline registra no `.meta.json` quando um arquivo de origem muda entre atualizações (histórico de mudanças dos dados).
