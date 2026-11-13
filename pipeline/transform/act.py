"""'Agir': tecnologias sociais sugeridas por regras simples e transparentes (SPEC §6.7). Sem custo.

Cada regra devolve o motivo em linguagem simples, citando o dado que a disparou. Regras que dependem de
fontes indisponíveis simplesmente não disparam (e a ficha diz quais dados faltam).
"""

from __future__ import annotations

from collections.abc import Mapping

CONTACT = "contato@institutosdw.org"


def _fmt(v: float) -> str:
    return f"{v:.0f}%"


def _has(ind: Mapping[str, float | None], k: str) -> bool:
    v = ind.get(k)
    return v is not None and v == v


def suggestions(ind: Mapping[str, float | None], ctx: Mapping[str, object]) -> list[dict]:
    out: list[dict] = []
    pop = ind.get("populacao") or 0
    semiarido = bool(ctx.get("semiarido"))
    sem_declaracao = bool(ctx.get("esgoto_sem_declaracao"))

    reasons = []
    if semiarido:
        reasons.append("o município está no Semiárido")
    if _has(ind, "decretos_seca_5a") and ind["decretos_seca_5a"] > 0:
        reasons.append(f"houve {int(ind['decretos_seca_5a'])} decreto(s) de seca ou estiagem nos últimos 5 anos")
    if reasons:
        out.append(
            {
                "id": "captacao_chuva",
                "title": "Captação de água da chuva e cisternas",
                "why": "Sugerido porque "
                + " e ".join(reasons)
                + ". Guardar a água da chuva garante reserva nos meses secos.",
            }
        )

    sem_rede, src = None, ""
    if _has(ind, "censo_agua_rede_pct"):
        sem_rede, src = 100 - ind["censo_agua_rede_pct"], "Censo 2022"
    elif _has(ind, "snis_agua_pct"):
        sem_rede, src = 100 - ind["snis_agua_pct"], "SNIS"
    sisagua = ind.get("sisagua_pct_fora_padrao") if _has(ind, "sisagua_pct_fora_padrao") else None
    if (sisagua is not None and sisagua > 10) or (sem_rede is not None and sem_rede >= 20):
        why = []
        if sem_rede is not None and sem_rede >= 20:
            why.append(f"{_fmt(sem_rede)} da população não é atendida pela rede de água ({src})")
        if sisagua is not None and sisagua > 10:
            why.append(f"{_fmt(sisagua)} das amostras de água ficaram fora do padrão (SISAGUA)")
        out.append(
            {
                "id": "tratamento_ponto_de_uso",
                "title": "Filtros e tratamento de água no ponto de uso",
                "why": "Sugerido porque "
                + " e ".join(why)
                + ". Filtros domésticos e comunitários tornam potável a água de poço, cisterna ou rio.",
            }
        )
    if sem_rede is not None and sem_rede >= 30:
        out.append(
            {
                "id": "unidade_autonoma_solar",
                "title": "Unidades autônomas de tratamento com energia solar",
                "why": f"Sugerido porque {_fmt(sem_rede)} da população está fora da rede de água ({src}). Unidades que tratam "
                "água com energia do sol atendem comunidades longe da rede e da energia elétrica. (O acesso à energia não foi "
                "avaliado: não há dado municipal integrado.)",
            }
        )

    tail = " Soluções individuais ou comunitárias tratam o esgoto onde a rede não chega."
    why = None
    if _has(ind, "censo_esgoto_adequado_pct"):
        if ind["censo_esgoto_adequado_pct"] < 50:
            why = (
                f"Sugerido porque só {_fmt(ind['censo_esgoto_adequado_pct'])} da população tem esgoto adequado (Censo 2022)."
                + tail
            )
    elif _has(ind, "snis_esgoto_pct"):
        if ind["snis_esgoto_pct"] < 50:
            why = (
                f"Sugerido porque só {_fmt(ind['snis_esgoto_pct'])} da população é atendida por rede coletora de esgoto "
                "(SNIS)." + tail
            )
    elif sem_declaracao:
        why = (
            "Sugerido porque nenhum prestador declarou atendimento de esgoto por rede neste município ao SNIS nos "
            "últimos anos, o que em geral indica ausência de rede coletora." + tail
        )
    if why:
        out.append(
            {
                "id": "saneamento_rural",
                "title": "Saneamento descentralizado (fossas ecológicas, biodigestores, banheiros)",
                "why": why,
            }
        )

    if _has(ind, "snis_perdas_pct") and ind["snis_perdas_pct"] >= 40 and pop >= 50_000:
        out.append(
            {
                "id": "reducao_perdas",
                "title": "Redução de perdas de água na rede",
                "why": f"Sugerido porque {_fmt(ind['snis_perdas_pct'])} da água tratada se perde antes de chegar às casas (SNIS). "
                "Reduzir vazamentos libera água e dinheiro para ampliar o atendimento.",
            }
        )
    out.append(
        {
            "id": "educacao_ambiental",
            "title": "Educação ambiental com escolas e lideranças",
            "why": "Sugerido para todos os territórios. Tecnologia dura mais quando a comunidade entende, cuida e cobra.",
        }
    )
    for s in out:
        s["contact"] = CONTACT
    return out
