"""Métricas de retorno e risco. Tudo em fração (0,10 = 10%), sobre preços ajustados por proventos."""
from __future__ import annotations

import numpy as np
import pandas as pd

DIAS_ANO = 252


def retorno_acumulado(precos: pd.Series) -> float:
    p = precos.dropna()
    return float(p.iloc[-1] / p.iloc[0] - 1) if len(p) >= 2 else np.nan


def anualizar(retorno: float, inicio: pd.Timestamp, fim: pd.Timestamp) -> float:
    anos = (fim - inicio).days / 365.25
    if anos <= 0 or pd.isna(retorno) or retorno <= -1:
        return np.nan
    return float((1 + retorno) ** (1 / anos) - 1)


def volatilidade(precos: pd.Series) -> float:
    """Desvio-padrão dos retornos diários × √252."""
    r = precos.dropna().pct_change().dropna()
    return float(r.std(ddof=1) * np.sqrt(DIAS_ANO)) if len(r) >= 20 else np.nan


def max_drawdown(precos: pd.Series) -> float:
    """Maior queda de um pico até um vale (número negativo)."""
    p = precos.dropna()
    return float((p / p.cummax() - 1).min()) if len(p) >= 2 else np.nan


def sharpe(retorno_aa: float, livre_risco_aa: float, vol: float) -> float:
    if pd.isna(retorno_aa) or pd.isna(livre_risco_aa) or pd.isna(vol) or vol == 0:
        return np.nan
    return float((retorno_aa - livre_risco_aa) / vol)


def recorte(precos: pd.Series, inicio: pd.Timestamp) -> pd.Series:
    """Série a partir do último preço até ``inicio`` (ele serve de base do período)."""
    p = precos.dropna()
    antes = p[p.index <= inicio]
    return p[p.index >= antes.index[-1]] if len(antes) else p


def resumo(precos: pd.Series, fim: pd.Timestamp, cdi_aa: float = np.nan) -> dict:
    """Métricas de uma série: período todo, 12 meses e ano corrente."""
    p = precos.dropna()
    p = p[p.index <= fim]
    if len(p) < 2:
        return {}
    ini = p.index[0]
    acum = retorno_acumulado(p)
    aa = anualizar(acum, ini, p.index[-1])
    vol = volatilidade(p)
    p12 = recorte(p, fim - pd.DateOffset(years=1))
    pano = recorte(p, pd.Timestamp(year=fim.year - 1, month=12, day=31))
    return {
        "desde": ini.date().isoformat(),
        "ate": p.index[-1].date().isoformat(),
        "ret_periodo": acum,
        "ret_aa": aa,
        "vol": vol,
        "sharpe": sharpe(aa, cdi_aa, vol),
        "drawdown": max_drawdown(p),
        "ret_12m": retorno_acumulado(p12) if ini <= fim - pd.DateOffset(months=11) else np.nan,
        "vol_12m": volatilidade(p12),
        "ret_ano": retorno_acumulado(pano) if ini.year < fim.year else np.nan,
    }


def indice_igual(precos: pd.DataFrame) -> pd.Series:
    """Índice de pesos iguais, rebalanceado todo dia: média dos retornos diários das colunas.

    Dia sem negócio conta como retorno zero (preço repetido); antes do primeiro preço a
    empresa não entra na média.
    """
    if precos.shape[1] == 0:
        return pd.Series(dtype=float)
    p = precos.ffill()
    r = p.pct_change()
    media = r.mean(axis=1, skipna=True).fillna(0.0)
    return (1 + media).cumprod()


def liquidez(fechamento: pd.Series, volume: pd.Series, dias: int = 60) -> dict:
    """Volume financeiro mediano (R$/dia) nos últimos ``dias`` pregões e presença em 12 meses."""
    fin = (fechamento * volume).fillna(0.0)
    ult = fin.tail(dias)
    ano = volume.tail(DIAS_ANO)
    return {
        "liq_mediana": float(ult.median()) if len(ult) else 0.0,
        "presenca_12m": float((ano.fillna(0) > 0).mean()) if len(ano) else 0.0,
    }
