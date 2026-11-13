# Perguntas para validação humana

Dúvidas que precisam de uma pessoa. Nenhuma delas bloqueia o trabalho: para cada uma foi
adotada uma decisão provisória (ver `DECISIONS.md`).

| # | Pergunta | Decisão provisória | Quem deve responder |
|---|---|---|---|
| Q1 | O ambiente de desenvolvimento usado na construção não tinha acesso de rede aos domínios do governo (IBGE, DATASUS, gov.br, BCB). Liberar esses domínios ou rodar o pipeline no GitHub Actions para gerar os dados oficiais? | Pipeline escrito contra as fontes oficiais; dados de desenvolvimento vindos de espelhos públicos com procedência registrada (ADR-002). | Equipe técnica / quem configurar o deploy |
