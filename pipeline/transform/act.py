"""'Agir': tecnologias sociais sugeridas por regras simples e transparentes (SPEC §6.7). Sem custo.

Cada regra devolve o motivo em linguagem simples, citando o dado que a disparou. Regras que dependem de
fontes indisponíveis simplesmente não disparam (e a ficha diz quais dados faltam).
"""

from __future__ import annotations

from collections.abc import Mapping

CONTACT = "contato@institutosdw.org"


def _fmt(v: float) -> str:
    return f"{v:.0f}%".replace(".", ",")


def suggestions(ind: Mapping[str, float | None], ctx: Mapping[str, object]) -> list[dict]:
    out: list[dict] = []
    agua_censo = ind.get("censo_agua_rede_pct")
    agua_snis = ind.get("snis_agua_pct")
    esgoto_censo = ind.get("censo_esgoto_adequado_pct")
    esgoto_snis = ind.get("snis_esgoto_pct")
    perdas = ind.get("snis_perdas_pct")
    pop = ind.get("populacao") or 0
    semiarido = bool(ctx.get("semiarido"))
    decretos_seca = ind.get("decretos_seca_5a")
    sisagua = ind.get("sisagua_pct_fora_padrao")

    reasons = []
    if semiarido:
        reasons.append("o município está no Semiárido")
    if decretos_seca:
        reasons.append(f"houve {int(decretos_seca)} decreto(s) de seca ou estiagem nos últimos 5 anos")
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

    sem_rede = None
    if agua_censo is not None:
        sem_rede = 100 - agua_censo
        src = "Censo 2022"
    elif agua_snis is not None:
        sem_rede = 100 - agua_snis
        src = "SNIS"
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
                "why": f"Sugerido porque {_fmt(sem_rede)} da população está fora da rede de água ({src}). Unidades que tratam água "
                "com energia do sol atendem comunidades longe da rede e da energia elétrica.",
            }
        )

    esgoto = esgoto_censo if esgoto_censo is not None else esgoto_snis
    esg_src = "Censo 2022" if esgoto_censo is not None else "SNIS"
    if esgoto is not None and esgoto < 50:
        out.append(
            {
                "id": "saneamento_rural",
                "title": "Saneamento descentralizado (fossas ecológicas, biodigestores, banheiros)",
                "why": f"Sugerido porque só {_fmt(esgoto)} da população tem esgoto adequado ({esg_src}). Soluções individuais ou "
                "comunitárias tratam o esgoto onde a rede não chega.",
            }
        )
    if perdas is not None and perdas >= 40 and pop >= 50_000:
        out.append(
            {
                "id": "reducao_perdas",
                "title": "Redução de perdas de água na rede",
                "why": f"Sugerido porque {_fmt(perdas)} da água tratada se perde antes de chegar às casas (SNIS). "
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
