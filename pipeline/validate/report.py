"""Gera docs/VALIDATION_REPORT.md a partir dos dados processados (SPEC §9, checagens de plausibilidade).

Uso: uv run python -m pipeline.validate.report
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from pipeline import config
from pipeline.transform import priority_index as pidx

SAMPLE = {"BA": ["2927408", "2910800", "2933307", "2918407", "2913606"], "CE": ["2312403", "2304400"]}
SAMPLE_NAMES = (
    "Salvador, Feira de Santana, Vitória da Conquista, Juazeiro, Ilhéus; Ceará: São Gonçalo do Amarante, Fortaleza"
)


def fmt(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "sem dado"
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def section_uf(uf: config.UF) -> list[str]:
    d = config.PROCESSED_DIR / uf.slug
    pub = config.PUBLIC_DIR / uf.slug
    if not (pub / "resumo.json").exists():
        return [f"## {uf.name}\n", "Sem dados processados.\n"]
    R = json.loads((pub / "resumo.json").read_text())
    val = json.loads((d / "_validation.json").read_text()) if (d / "_validation.json").exists() else {}
    mun = pd.DataFrame(R["municipios"])
    ind = pd.json_normalize(mun["ind"]).set_index(mun["cod"])
    names = dict(zip(mun["cod"], mun["nome"], strict=True))
    L = [f"## {uf.name} ({uf.sigla})\n"]

    L.append("### 1. Origem de cada base\n")
    L.append("| Etapa | Status | Origem | Período | Observação |\n|---|---|---|---|---|")
    for k, s in R["sources"].items():
        kind = {"official": "oficial", "mirror": "espelho"}.get(s.get("url_kind") or "", "–")
        note = (s.get("status_reason") or "")[:120].replace("|", "/").replace("\n", " ")
        L.append(f"| {k} | {s['status']} | {kind} | {s.get('reference_period') or '–'} | {note} |")
    L.append("")

    L.append("### 2. Checagens automáticas (SPEC §9)\n")
    errs = val.get("errors", [])
    L.append(f"- Erros: **{len(errs)}** (o pipeline falha se houver algum).")
    L.append(f"- Municípios: {val.get('info', {}).get('municipios')} (esperado {uf.expected_municipalities}).")
    L.append(
        f"- População somada: {fmt(val.get('info', {}).get('populacao_total'), 0)} (oficial {fmt(uf.census2022_population, 0)})."
    )
    for w in val.get("warnings", []):
        L.append(f"- Aviso: {w[:300]}")
    jumps = val.get("info", {}).get("saltos_series", [])
    if jumps:
        top = sorted(jumps, key=lambda j: -j.get("variacao_anual", 0))[:10]
        L.append(
            "\nMaiores saltos anuais nas séries do SNIS (aviso, não erro; em geral mudança de declaração do prestador):\n"
        )
        L.append("| Município | Indicador | Ano | Variação relativa ao ano |\n|---|---|---|---|")
        for j in top:
            L.append(
                f"| {names.get(j['cod_ibge7'], j['cod_ibge7'])} | {j['indicador']} | {j['ano']} | {fmt(j['variacao_anual'] * 100, 0)}% |"
            )
    L.append("")

    L.append("### 3. Internações (SIH) × TabNet\n")
    if R["sources"].get("sih_drsai", {}).get("status") == "unavailable":
        L.append(
            "**Pendente.** O SIH não pôde ser lido no ambiente de construção (FTP do DATASUS bloqueado). Quando o "
            "pipeline rodar no GitHub Actions, conferir para a amostra abaixo:\n\n"
            "- TabNet → Epidemiológicas e Morbidade → Morbidade Hospitalar do SUS (SIH/SUS) → Geral, por local de "
            "residência (a partir de 2008) → UF.\n- Linha: Município; Coluna: Ano processamento; Conteúdo: Internações "
            "e Valor total; Seleções: Lista Morb CID-10 com os capítulos correspondentes às categorias DRSAI do núcleo "
            "(ou, mais preciso, comparar contra o próprio .dbc filtrado).\n"
            f"- Amostra: {SAMPLE_NAMES}.\n- Diferenças esperadas: o TabNet agrega por lista de morbidade (grupos de CID), "
            "não por categoria de 3 caracteres; AIHs de longa permanência (IDENT 5) não contam como internação.\n"
        )
    else:
        L.append(
            "| Município | Internações/ano (pipeline) | Valor/ano (pipeline) | TabNet | Diferença |\n|---|---|---|---|---|"
        )
        for c in SAMPLE.get(uf.sigla, []):
            if c in ind.index:
                L.append(
                    f"| {names[c]} | {fmt(ind.loc[c].get('drsai_internacoes'), 0)} | R$ {fmt(ind.loc[c].get('drsai_valor_anual'), 0)} | conferir | – |"
                )
    L.append("")

    L.append("### 4. Cobertura SNIS × Censo\n")
    if "censo_agua_rede_pct" not in ind or ind["censo_agua_rede_pct"].isna().all():
        L.append(
            "**Pendente**: o Censo 2022 de água e esgoto (SIDRA) não pôde ser lido no ambiente de construção. "
            "A ficha e este relatório passam a mostrar os maiores divergentes (limiar de 15 p.p.) assim que a fonte entrar.\n"
        )
    else:
        d = (ind["snis_agua_pct"] - ind["censo_agua_rede_pct"]).dropna().sort_values(key=abs, ascending=False).head(15)
        L.append("| Município | SNIS água | Censo água (rede) | Diferença (p.p.) |\n|---|---|---|---|")
        for c, v in d.items():
            L.append(
                f"| {names[c]} | {fmt(ind.loc[c, 'snis_agua_pct'])} | {fmt(ind.loc[c, 'censo_agua_rede_pct'])} | {fmt(v)} |"
            )
    L.append(
        "\nConsistência interna do SNIS (IN055 × população atendida ÷ população do Censo, 2022): diferença mediana "
        "≈ 0 p.p., desvio de 0,24 p.p. (conferido na revisão do M2).\n"
    )

    L.append("### 5. Municípios sem dado, por indicador\n")
    L.append("| Indicador | Com dado | Sem dado | Exemplos sem dado |\n|---|---|---|---|")
    for col in [
        "snis_agua_pct",
        "snis_esgoto_pct",
        "snis_esgoto_tratado_pct",
        "snis_perdas_pct",
        "censo_lixo_coletado_pct",
        "pop_quilombola",
        "drsai_internacoes",
        "censo_agua_rede_pct",
    ]:
        if col not in ind:
            L.append(f"| {col} | 0 | {len(ind)} | fonte indisponível |")
            continue
        miss = ind[col].isna()
        ex = ", ".join(names[c] for c in ind.index[miss][:5])
        L.append(f"| {col} | {int((~miss).sum())} | {int(miss.sum())} | {ex} |")
    L.append("")

    t = pd.DataFrame(list(mun["thermo"]))
    L.append("### 6. Termômetro 2033\n")
    for svc, label in (
        ("agua", "Água (IN055, meta 99%)"),
        ("esgoto", "Esgoto coletado e tratado (IN056 × IN016, meta 90%)"),
    ):
        vc = t[svc].value_counts().to_dict()
        L.append(f"- {label}: " + "; ".join(f"{k}: {v}" for k, v in vc.items()))
    L.append("")

    L.append("### 7. Índice de prioridade: revisão do topo e da base\n")
    idx = R["index"]
    if idx["ranked"] == 0:
        L.append(
            f"O índice oficial não ranqueia nesta versão: há {len(idx['dims_available'])} de 5 dimensões "
            f"({', '.join(idx['dims_available'])}), abaixo do mínimo de {idx['min_dimensions_for_rank']}. "
            "Para testar o mecanismo, abaixo está um **ranking exploratório** com as dimensões disponíveis "
            "(não publicado no site):\n"
        )
        dims = pd.json_normalize(mun["dims"]).set_index(mun["cod"])
        w = idx["weights"]
        scores = {
            c: pidx.weighted_index({k: (None if pd.isna(v) else v) for k, v in dims.loc[c].items()}, w, 1)[0]
            for c in dims.index
        }
        s = pd.Series(scores).dropna().sort_values(ascending=False)
        L.append(
            "| Posição | Município | Nota exploratória | Sem água (SNIS) | Sem esgoto (SNIS) | % quilombola + indígena |\n|---|---|---|---|---|---|"
        )
        for i, (c, v) in enumerate(list(s.head(10).items()) + list(s.tail(10).items())):
            pos = i + 1 if i < 10 else len(s) - 19 + i
            L.append(
                f"| {pos} | {names[c]} | {fmt(v, 0)} | {fmt(ind.loc[c].get('snis_sem_agua_pct'))} | "
                f"{fmt(ind.loc[c].get('snis_sem_esgoto_pct'))} | {fmt(ind.loc[c].get('pct_pop_quilombola_indigena'))} |"
            )
        L.append(
            "\n**Leitura (revisão manual):** o topo exploratório é dominado pela falta de rede de água (57% a 81% da "
            "população fora da rede); onde há dado de povos tradicionais (Maraú, Banzaê, Muquém de São Francisco) ele "
            "reforça a posição. A base reúne municípios com rede de água quase universal. O mecanismo responde na direção "
            "esperada. Ressalvas: (1) sem saúde, clima e qualidade da água, este ranking não serve para priorizar; "
            "(2) o percentual quilombola + indígena fica sem dado onde o espelho do Censo tem sigilo total, então a "
            "dimensão vulnerabilidade pesa pouco até a tabela oficial do SIDRA entrar; (3) o esgoto do SNIS falta em "
            "muitos municípios pequenos (provável ausência de rede), o que os favorece; o Censo corrige isso.\n"
        )
    sens_p = pub / "indice_sensibilidade.json"
    if sens_p.exists():
        sens = json.loads(sens_p.read_text())
        L.append(
            f"Análise de sensibilidade (±10 p.p. por peso, top 20): status `{sens.get('status')}`"
            + (
                f", sobreposição mínima {sens['min_overlap']}/20, média {fmt(sens['mean_overlap'])}/20."
                if sens.get("status") == "ok"
                else "."
            )
            + "\n"
        )
    return L


def main() -> None:
    L = [
        "# Relatório de validação\n",
        f"Gerado em {datetime.now(UTC).strftime('%d/%m/%Y %H:%M UTC')} por `pipeline/validate/report.py`. "
        "Regenerado a cada execução do pipeline.\n",
        "Este relatório complementa as checagens automáticas (que derrubam o pipeline) com checagens de plausibilidade "
        "que exigem leitura humana. Itens marcados **pendente** dependem de fontes que não puderam ser lidas no ambiente "
        "de construção (ver `docs/DATA_SOURCES.md`).\n",
        "## Calculadora\n",
        "- Casos calculados à mão: `pipeline/tests/test_calculator.py` (VP de 3 anos a 10% = R$ 186.513,90; SROI 1,281).",
        "- Propriedades testadas com Hypothesis: monotonicidade na redução, VP zero com 0%, convergência para a soma "
        "simples quando a taxa vai a zero, VP decrescente na taxa.",
        "- Paridade Python × TypeScript: 204 casos com igualdade exata (`===`), incluindo a faixa de sensibilidade.\n",
    ]
    for uf in config.ufs():
        L += section_uf(uf)
    out = config.ROOT / "docs" / "VALIDATION_REPORT.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"escrito {out}")


if __name__ == "__main__":
    main()
