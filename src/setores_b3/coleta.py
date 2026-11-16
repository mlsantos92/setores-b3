"""Coleta: preços e fundamentos no Yahoo Finance (via yfinance) e CDI no Banco Central (SGS 12).

Só este módulo fala com a rede. O resto do projeto recebe DataFrames e dicionários,
o que deixa os cálculos testáveis sem internet.
"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd
import requests

SUFIXO = ".SA"
IBOV = "^BVSP"
CAMPOS = ["trailingPE", "trailingEps", "priceToBook", "enterpriseToEbitda", "dividendYield", "returnOnEquity",
          "profitMargins", "debtToEquity", "marketCap", "currentPrice", "longName", "sector", "industry"]
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


def _simbolo(t: str) -> str:
    return t if t.startswith("^") else t + SUFIXO


def precos(tickers: list[str], anos: int = 5, lote: int = 40, pausa: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fechamento ajustado por proventos e volume (nº de ações), uma coluna por código."""
    import yfinance as yf

    fech, vol = {}, {}
    for i in range(0, len(tickers), lote):
        grupo = tickers[i:i + lote]
        for tentativa in range(3):
            try:
                d = yf.download([_simbolo(t) for t in grupo], period=f"{anos}y", interval="1d", auto_adjust=True,
                                progress=False, group_by="ticker", threads=True)
                break
            except Exception as erro:  # rede ou limite de requisições
                print(f"lote {i}: {type(erro).__name__}; nova tentativa")
                time.sleep(5 * (tentativa + 1))
        else:
            continue
        for t in grupo:
            s = _simbolo(t)
            if s not in d.columns.get_level_values(0):
                continue
            c = d[s]["Close"].dropna()
            if len(c):
                fech[t] = c
                vol[t] = d[s]["Volume"].reindex(c.index)
        time.sleep(pausa)
    f, v = pd.DataFrame(fech), pd.DataFrame(vol)
    for df in (f, v):
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return f.sort_index(), v.sort_index()


def fundamentos(tickers: list[str], pausa: float = 0.25) -> dict[str, dict]:
    """Indicadores do Yahoo por código. Código que falha fica de fora (o pipeline reusa o último valor)."""
    import yfinance as yf

    out = {}
    for t in tickers:
        try:
            info = yf.Ticker(_simbolo(t)).info or {}
        except Exception as erro:
            print(f"fundamentos {t}: {type(erro).__name__}")
            time.sleep(2)
            continue
        dados = {k: info.get(k) for k in CAMPOS}
        if any(v is not None for k, v in dados.items() if k not in ("longName", "sector", "industry")):
            out[t] = dados
        time.sleep(pausa)
    return out


def cdi_diario(inicio: date, fim: date, timeout: int = 30) -> pd.Series:
    """CDI diário (% ao dia) do SGS, série 12."""
    params = {"formato": "json", "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": fim.strftime("%d/%m/%Y")}
    r = requests.get(URL_SGS.format(codigo=12), params=params, timeout=timeout)
    r.raise_for_status()
    d = pd.DataFrame(r.json())
    d["data"] = pd.to_datetime(d["data"], dayfirst=True)
    return d.set_index("data")["valor"].astype(float)
