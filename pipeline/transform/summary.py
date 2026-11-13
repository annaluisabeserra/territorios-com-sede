"""Resumo em linguagem simples por templates determinísticos (SPEC §6.3). Nada é gerado por IA."""

from __future__ import annotations

from collections.abc import Mapping


def num(v: float, digits: int = 0) -> str:
    """Arredondamento "meio para cima", igual ao Intl.NumberFormat do site (99,85 → 99,9 nos dois lados)."""
    from decimal import ROUND_HALF_UP, Decimal

    q = Decimal(1).scaleb(-digits)
    d = Decimal(repr(float(v))).quantize(q, rounding=ROUND_HALF_UP)
    s = f"{d:,.{digits}f}"
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
    """Frases determinísticas. `extra`: years (ano por indicador), sih_period, esgoto_sem_declaracao."""
    years = extra.get("years") or {}

    def has(k: str) -> bool:
        v = ind.get(k)
        return v is not None and v == v  # exclui NaN

    parts: list[str] = []
    if has("populacao"):
        parts.append(f"{nome} tem {num(ind['populacao'])} moradores, segundo o Censo 2022.")

    if has("censo_esgoto_adequado_pct"):
        sem = 100 - ind["censo_esgoto_adequado_pct"]
        frac = one_in(sem)
        lead = f"{frac.capitalize()} moradores" if frac else f"{pct(sem)} dos moradores"
        parts.append(f"{lead} não têm esgoto adequado (Censo 2022).")
    elif has("snis_esgoto_tratado_pct"):
        # Abre pelo indicador da meta (coleta E tratamento); a coleta vem como contexto (revisão M4).
        tr, col = ind["snis_esgoto_tratado_pct"], ind.get("snis_esgoto_pct")
        y = years.get("snis_esgoto_tratado_pct") or years.get("snis_esgoto_pct")
        txt = f"{pct(tr)} da população tem o esgoto coletado e tratado (SNIS {y})."
        if col is not None and col == col and col - tr >= 5:
            if tr < 0.05:
                txt += (
                    f" A rede coleta o esgoto de {pct(col)} da população, mas nada é tratado: tudo volta para "
                    "rios e para o solo."
                )
            else:
                txt += (
                    f" A rede coleta o esgoto de {pct(col)} da população, mas parte do que é coletado não recebe "
                    "tratamento antes de voltar para rios e para o solo."
                )
        parts.append(txt)
    elif has("snis_esgoto_pct"):
        parts.append(
            f"O prestador de serviço declara atender {pct(ind['snis_esgoto_pct'])} da população com rede de "
            f"coleta de esgoto (SNIS {years.get('snis_esgoto_pct')}), mas não informou quanto é tratado."
        )
    elif extra.get("esgoto_sem_declaracao"):
        parts.append(
            "Nenhum prestador declarou atendimento de esgoto por rede ao SNIS nos últimos anos, o que em geral "
            "indica que o município não tem rede coletora."
        )
    else:
        parts.append("Não há dado oficial recente sobre o atendimento de esgoto do município.")

    if has("censo_agua_rede_pct"):
        parts.append(f"{pct(ind['censo_agua_rede_pct'])} dos moradores recebem água da rede geral (Censo 2022).")
    elif has("snis_agua_pct"):
        parts.append(
            f"O atendimento de água declarado ao SNIS é de {pct(ind['snis_agua_pct'])} ({years.get('snis_agua_pct')})."
        )

    if has("drsai_internacoes") and has("drsai_valor_anual"):
        parts.append(
            f"Em média, {num(ind['drsai_internacoes'])} pessoas por ano são internadas no SUS por doenças ligadas à "
            f"falta de saneamento, o que custa {brl(ind['drsai_valor_anual'])} por ano ({extra.get('sih_period')})."
        )
    else:
        parts.append(
            "Os dados de internações por doenças ligadas ao saneamento ainda não foram processados para esta versão."
        )

    ta, te = thermo.get("agua", {}), thermo.get("esgoto", {})
    if ta.get("status") and te.get("status"):
        parts.append(
            f"Pela tendência do SNIS, a meta de água do Marco Legal {THERMO_TXT[ta['status']]}, e a de "
            f"esgoto coletado e tratado {THERMO_TXT[te['status']]}."
        )
    return parts
