"""Limpeza dos indicadores fundamentalistas e comparação com a mediana do setor."""
from __future__ import annotations

import math

LIMITES = {"pl": (0, 200), "pvp": (0, 50), "ev_ebitda": (0, 100), "dy": (0, 0.30),
           "roe": (-2, 2), "margem": (-5, 1), "div_pl": (0, 20)}


def _num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def _faixa(nome: str, x: float | None) -> float | None:
    if x is None:
        return None
    lo, hi = LIMITES[nome]
    return x if lo < x <= hi or (nome in ("roe", "margem", "dy", "div_pl") and lo <= x <= hi) else None


def limpar(info: dict) -> dict:
    """Converte o retorno do Yahoo em indicadores comparáveis. Valor fora da faixa plausível vira None.

    P/L só existe com lucro: empresa com prejuízo fica sem P/L e marcada em ``prejuizo``.
    O dividend yield não vem daqui: é calculado dos proventos pagos (ver ``dividend_yield``).
    """
    lpa = _num(info.get("trailingEps"))
    div = _num(info.get("debtToEquity"))
    return {
        "pl": _faixa("pl", _num(info.get("trailingPE"))),
        "pvp": _faixa("pvp", _num(info.get("priceToBook"))),
        "ev_ebitda": _faixa("ev_ebitda", _num(info.get("enterpriseToEbitda"))),
        "roe": _faixa("roe", _num(info.get("returnOnEquity"))),
        "margem": _faixa("margem", _num(info.get("profitMargins"))),
        "div_pl": _faixa("div_pl", div / 100 if div is not None else None),
        "valor_mercado": _num(info.get("marketCap")),
        "prejuizo": bool(lpa is not None and lpa < 0),
    }


def mediana(valores: list[float | None]) -> float | None:
    v = sorted(x for x in (_num(y) for y in valores) if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def frente_ao_setor(valor: float | None, mediana_setor: float | None) -> float | None:
    """Quanto o indicador da empresa está acima (+) ou abaixo (−) da mediana do setor."""
    valor, mediana_setor = _num(valor), _num(mediana_setor)
    if valor is None or not mediana_setor:
        return None
    return valor / mediana_setor - 1


def dividend_yield(proventos_12m: float | None, preco: float | None) -> float | None:
    """Proventos por ação pagos em 12 meses ÷ preço atual. Acima de 30% é tratado como dado suspeito."""
    p, x = _num(proventos_12m), _num(preco)
    if p is None or x is None or x <= 0 or p < 0:
        return None
    return _faixa("dy", p / x)


DIVERGENCIA = 0.25


def de_resultado(valor_mercado, lucro_12m, patrimonio, receita_12m=None) -> dict:
    """Múltiplos a partir das demonstrações oficiais: lucro e patrimônio da controladora.

    Devolve só o que dá para calcular. P/L exige lucro positivo; P/VP e ROE, patrimônio positivo.
    """
    vm, lucro, pl, rec = _num(valor_mercado), _num(lucro_12m), _num(patrimonio), _num(receita_12m)
    out = {}
    if lucro is not None:
        out["prejuizo"] = lucro < 0
        out["pl"] = _faixa("pl", vm / lucro) if vm and lucro > 0 else None
        if rec and rec > 0:
            out["margem"] = _faixa("margem", lucro / rec)
    if pl is not None and pl > 0:
        if vm:
            out["pvp"] = _faixa("pvp", vm / pl)
        if lucro is not None:
            out["roe"] = _faixa("roe", lucro / pl)
    return out


def diverge(a, b, tolerancia: float = DIVERGENCIA) -> bool:
    """Dois valores do mesmo indicador que diferem mais que a tolerância (25%)."""
    a, b = _num(a), _num(b)
    return bool(a and b and abs(a / b - 1) > tolerancia)
