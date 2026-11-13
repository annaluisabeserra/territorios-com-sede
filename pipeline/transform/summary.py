"""Resumo em linguagem simples por templates determinísticos (SPEC §6.3). Nada é gerado por IA."""

from __future__ import annotations

from collections.abc import Mapping


def num(v: float, digits: int = 0) -> str:
    s = f"{v:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float) -> str:
    return num(v, 1) + "%"


def brl(v: float) -> str:
    if v >= 1e6:
        return f"R$ {num(v / 1e6, 1)} milhões"
    if v >= 1e3:
        return f"R$ {num(v / 1e3, 0)} mil"
    return f"R$ {num(v, 0)}"


def one_in(p: float) -> str | None:
    if p <= 0:
        return None
    n = round(100 / p)
    return f"1 em cada {n}" if 2 <= n <= 20 else None


THERMO_TXT = {
    "atingida": "já foi alcançada",
    "no_ritmo": "deve ser cumprida até 2033",
    "atrasado": "não será cumprida até 2033 no ritmo atual",
    "sem_dados": "não pode ser projetada (faltam dados)",
}


def municipal_summary(
    nome: str, ind: Mapping[str, float | None], thermo: Mapping[str, dict], extra: Mapping
) -> list[str]:
    parts: list[str] = []
    pop = ind.get("populacao")
    if pop:
        parts.append(f"{nome} tem {num(pop)} moradores, segundo o Censo 2022.")

    esg = ind.get("censo_esgoto_adequado_pct")
    if esg is not None:
        sem = 100 - esg
        frac = one_in(sem)
        lead = f"{frac.capitalize()} moradores" if frac else f"{pct(sem)} dos moradores"
        parts.append(f"{lead} não têm esgoto adequado (Censo 2022).")
    elif ind.get("snis_esgoto_pct") is not None:
        parts.append(
            f"O prestador de serviço declara atender {pct(ind['snis_esgoto_pct'])} da população com coleta de esgoto "
            f"(SNIS {extra.get('snis_year')})."
        )
    else:
        parts.append("Não há dado oficial recente sobre o atendimento de esgoto do município.")

    agua = ind.get("censo_agua_rede_pct")
    if agua is not None:
        parts.append(f"{pct(agua)} dos moradores recebem água da rede geral (Censo 2022).")
    elif ind.get("snis_agua_pct") is not None:
        parts.append(
            f"O atendimento de água declarado ao SNIS é de {pct(ind['snis_agua_pct'])} ({extra.get('snis_year')})."
        )

    inter = ind.get("drsai_internacoes")
    valor = ind.get("drsai_valor_anual")
    if inter is not None and valor is not None:
        parts.append(
            f"Em média, {num(inter)} pessoas por ano são internadas no SUS por doenças ligadas à falta de saneamento, "
            f"o que custa {brl(valor)} por ano ({extra.get('sih_period')})."
        )
    else:
        parts.append(
            "Os dados de internações por doenças ligadas ao saneamento ainda não foram processados para esta versão."
        )

    ta, te = thermo.get("agua", {}), thermo.get("esgoto", {})
    if ta.get("status") and te.get("status"):
        parts.append(
            f"Pela tendência do SNIS, a meta de água do Marco Legal {THERMO_TXT[ta['status']]}, e a de "
            f"esgoto {THERMO_TXT[te['status']]}."
        )
    return parts
