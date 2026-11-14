#!/usr/bin/env bash
# Testa se cada servidor oficial responde a partir da máquina que roda a atualização de dados.
# Não derruba nada: só imprime uma tabela "ok / sem resposta" no log, para diagnóstico.
set -u
check() {
  local nome="$1" url="$2"
  local code
  code=$(curl -sS -o /dev/null -m 25 --connect-timeout 15 -w "%{http_code}" "$url" 2>/dev/null) || code="000"
  if [ "$code" = "000" ]; then printf "%-34s SEM RESPOSTA  %s\n" "$nome" "$url"; else printf "%-34s ok (HTTP %s)  %s\n" "$nome" "$code" "$url"; fi
}
echo "== Diagnóstico de rede ($(uname -s), $(date -u +%Y-%m-%dT%H:%MZ)) =="
check "IBGE API (localidades)" "https://servicodados.ibge.gov.br/api/v1/localidades/estados/29"
check "IBGE SIDRA (agregados)" "https://servicodados.ibge.gov.br/api/v3/agregados?pesquisa=CD"
check "DATASUS FTP (SIH/SIM)" "ftp://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DORES/"
check "Ministério das Cidades (SINISA)" "https://www.gov.br/cidades/pt-br"
check "OpenDataSUS (SISAGUA)" "https://opendatasus.saude.gov.br/api/3/action/status_show"
check "MIDR dados abertos (S2ID)" "https://dadosabertos.mdr.gov.br/api/3/action/status_show"
check "ANA Monitor de Secas" "https://monitordesecas.ana.gov.br/"
check "INEP downloads" "https://download.inep.gov.br/"
check "Tesouro SICONFI" "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"
check "Banco Central (IPCA)" "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1?formato=json"
check "Base dos Dados (cópias)" "https://storage.googleapis.com/basedosdados-public/"
exit 0
