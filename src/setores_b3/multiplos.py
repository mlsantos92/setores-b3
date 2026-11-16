"""Limpeza dos indicadores fundamentalistas e comparação com a mediana do setor."""
from __future__ import annotations

import math

LIMITES = {"pl": (0, 200), "pvp": (0, 50), "ev_ebitda": (0, 100), "dy": (0, 0.40),
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
    Dividend yield vem em pontos percentuais no Yahoo (8,09 = 8,09%).
    """
    lpa = _num(info.get("trailingEps"))
    dy = _num(info.get("dividendYield"))
    div = _num(info.get("debtToEquity"))
    return {
        "pl": _faixa("pl", _num(info.get("trailingPE"))),
        "pvp": _faixa("pvp", _num(info.get("priceToBook"))),
        "ev_ebitda": _faixa("ev_ebitda", _num(info.get("enterpriseToEbitda"))),
        "dy": _faixa("dy", dy / 100 if dy is not None else None),
        "roe": _faixa("roe", _num(info.get("returnOnEquity"))),
        "margem": _faixa("margem", _num(info.get("profitMargins"))),
        "div_pl": _faixa("div_pl", div / 100 if div is not None else None),
        "valor_mercado": _num(info.get("marketCap")),
        "prejuizo": bool(lpa is not None and lpa < 0),
    }


def mediana(valores: list[float | None]) -> float | None:
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def frente_ao_setor(valor: float | None, mediana_setor: float | None) -> float | None:
    """Quanto o indicador da empresa está acima (+) ou abaixo (−) da mediana do setor."""
    if valor is None or not mediana_setor:
        return None
    return valor / mediana_setor - 1
