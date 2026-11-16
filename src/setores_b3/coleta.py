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
CAMPOS = ["trailingPE", "trailingEps", "priceToBook", "enterpriseToEbitda", "returnOnEquity",
          "profitMargins", "debtToEquity", "marketCap", "currentPrice", "longName", "sector", "industry"]
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


def _simbolo(t: str) -> str:
    return t if t.startswith("^") else t + SUFIXO


def precos(tickers: list[str], anos: int = 5, lote: int = 40, pausa: float = 1.0) -> dict[str, pd.DataFrame]:
    """Uma coluna por código em cada tabela:

    - ``ajustado``: fechamento ajustado por proventos (base do retorno);
    - ``bruto``: fechamento como negociado (base da liquidez e do dividend yield);
    - ``volume``: número de ações negociadas;
    - ``proventos``: dividendos e JCP por ação, na data ex.
    """
    import yfinance as yf

    tab = {"ajustado": {}, "bruto": {}, "volume": {}, "proventos": {}}
    for i in range(0, len(tickers), lote):
        grupo = tickers[i:i + lote]
        for tentativa in range(3):
            try:
                d = yf.download([_simbolo(t) for t in grupo], period=f"{anos}y", interval="1d", auto_adjust=False,
                                actions=True, progress=False, group_by="ticker", threads=True)
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
            q = d[s]
            c = q["Adj Close"].dropna()
            if not len(c):
                continue
            tab["ajustado"][t] = c
            tab["bruto"][t] = q["Close"].reindex(c.index)
            tab["volume"][t] = q["Volume"].reindex(c.index)
            if "Dividends" in q:
                tab["proventos"][t] = q["Dividends"].reindex(c.index).fillna(0.0)
        time.sleep(pausa)
    out = {}
    for nome, colunas in tab.items():
        df = pd.DataFrame(colunas)
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        out[nome] = df.sort_index()
    return out


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
