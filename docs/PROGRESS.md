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

- Glossário inline na calculadora (deadweight, atribuição, drop-off) e no termômetro.
- Cabeçalho mais compacto no celular ao rolar.
- Fonte e ano por célula na tabela da ficha; link direto à fonte oficial ao lado do espelho.
- Rótulos dos eixos do gráfico em tamanho mínimo de 12 px no celular.
- `aria-label` único por tabela; ordem de foco dos botões da calculadora.
- Total oficial de pessoas indígenas e de quilombolas (SIDRA) substituindo as somas do espelho (entra no Actions).
- Comparação do saneamento de domicílios quilombolas e indígenas com o município (Censo 2022).
- Etnia das terras indígenas pelo campo oficial da FUNAI (entra no Actions).
- Uso da ANA como reforço do componente de esgoto no índice; parâmetro de defasagem na calculadora; Theil–Sen como alternativa robusta no termômetro.
- Campo de metodologia na série (quebra SNIS 2022 e transição para o SINISA).
- Leitores de SISAGUA, S2ID, INCRA, Palmares, CadÚnico e SICONFI.
- Limite de taxa no `/event`; lista de origens de CORS; formulário de retirada sem login; seletor da escola sem JavaScript.
- Checagem do sha256 esperado dos espelhos; ações do GitHub fixadas por SHA.
