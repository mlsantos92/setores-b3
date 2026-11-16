"""Monta o estudo: escolhe o código mais líquido de cada empresa, calcula as métricas
por empresa e agrega por setor e por lista (large/mid × small/micro)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import metricas, multiplos

LIQ_MINIMA = 100_000      # R$/dia, mediana dos últimos 60 pregões
PRESENCA_MINIMA = 0.90    # fração dos pregões dos últimos 12 meses com negócio
INDICADORES = ["pl", "pvp", "ev_ebitda", "dy", "roe", "margem", "div_pl"]


def _limpo(x):
    if isinstance(x, (float, np.floating)):
        return None if (math.isnan(x) or math.isinf(x)) else round(float(x), 6)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def escolher_tickers(universo: pd.DataFrame, fech: pd.DataFrame, vol: pd.DataFrame,
                     ajustado: pd.DataFrame | None = None) -> pd.DataFrame:
    """Para cada empresa, o código com maior volume financeiro mediano. Sem dado: ticker None.

    ``fech`` é o preço como negociado (liquidez); ``ajustado`` serve para achar saltos suspeitos.
    """
    ajustado = fech if ajustado is None else ajustado
    linhas = []
    for e in universo.itertuples():
        melhor, liq_melhor = None, None
        for t in e.tickers:
            if t not in fech.columns or not fech[t].notna().any():
                continue
            liq = metricas.liquidez(fech[t], vol[t])
            if melhor is None or liq["liq_mediana"] > liq_melhor["liq_mediana"]:
                melhor, liq_melhor = t, liq
        liq_melhor = liq_melhor or {"liq_mediana": 0.0, "presenca_12m": 0.0}
        linhas.append({"ticker": melhor, **liq_melhor})
    extra = pd.DataFrame(linhas)
    extra["ticker"] = pd.Series([l["ticker"] for l in linhas], dtype=object)
    out = pd.concat([universo.reset_index(drop=True), extra], axis=1)
    out["suspeito"] = [bool(isinstance(t, str) and metricas.salto_suspeito(ajustado[t])) for t in out["ticker"]]
    out["elegivel"] = (out["ticker"].notna() & (out["liq_mediana"] >= LIQ_MINIMA)
                       & (out["presenca_12m"] >= PRESENCA_MINIMA) & ~out["suspeito"])
    return out


def _agregado(nome: dict, emp: pd.DataFrame, fech: pd.DataFrame, fim: pd.Timestamp, cdi_aa: float) -> dict:
    eleg = emp[emp["elegivel"]]
    indice = metricas.indice_igual(fech[list(eleg["ticker"])]) if len(eleg) else pd.Series(dtype=float)
    r = metricas.resumo(indice, fim, cdi_aa) if len(indice) else {}
    meds = {f"{k}_mediana": multiplos.mediana(list(eleg[k])) for k in INDICADORES}
    return {**nome, "empresas": int(len(emp)), "elegiveis": int(len(eleg)),
            "com_prejuizo": int(eleg["prejuizo"].sum()) if len(eleg) else 0, **r, **meds}, indice


def montar(universo: pd.DataFrame, fech: pd.DataFrame, vol: pd.DataFrame, fundamentos: dict,
           cdi_aa: float, fim: pd.Timestamp, bruto: pd.DataFrame | None = None,
           proventos: pd.DataFrame | None = None) -> dict:
    """Devolve {"empresas": [...], "setores": [...], "listas": [...], "series": {...}}.

    ``fech`` é o preço ajustado por proventos. ``bruto`` (preço negociado) e ``proventos``
    são opcionais: sem eles a liquidez usa o preço ajustado e não há dividend yield.
    """
    fech = fech[fech.index <= fim]
    vol = vol[vol.index <= fim]
    bruto = fech if bruto is None else bruto[bruto.index <= fim]
    emp = escolher_tickers(universo, bruto, vol, fech)

    reg = []
    for e in emp.itertuples():
        base = {"empresa": e.empresa, "lista": e.lista, "setor": e.setor, "subsetor": e.subsetor,
                "ticker": e.ticker if isinstance(e.ticker, str) else None, "tickers_lista": " ".join(getattr(e, "tickers_lista", e.tickers)),
                "liq_mediana": e.liq_mediana, "presenca_12m": e.presenca_12m, "elegivel": bool(e.elegivel),
                "suspeito": bool(e.suspeito)}
        if not isinstance(e.ticker, str):
            reg.append({**base, **{k: None for k in INDICADORES}, "prejuizo": False, "valor_mercado": None})
            continue
        r = metricas.resumo(fech[e.ticker], fim, cdi_aa)
        m = multiplos.limpar(fundamentos.get(e.ticker, {}))
        m["dy"] = None
        if proventos is not None and e.ticker in proventos.columns:
            pago = proventos[e.ticker]
            pago = pago[(pago.index > fim - pd.DateOffset(years=1)) & (pago.index <= fim)].sum()
            m["dy"] = multiplos.dividend_yield(float(pago), float(bruto[e.ticker].dropna().iloc[-1]))
        reg.append({**base, **r, **m, "ultimo_preco_em": fech[e.ticker].dropna().index[-1].date().isoformat()})
    emp = pd.DataFrame(reg)
    emp["ticker"] = pd.Series([r["ticker"] for r in reg], dtype=object)

    setores, series = [], {}
    for setor, g in emp.groupby("setor", sort=True):
        ag, idx = _agregado({"setor": setor, "lista": "Todas"}, g, fech, fim, cdi_aa)
        setores.append(ag)
        series[setor] = idx
        for lista, gl in g.groupby("lista", sort=True):
            ag, _ = _agregado({"setor": setor, "lista": lista}, gl, fech, fim, cdi_aa)
            setores.append(ag)
    listas = []
    for lista, g in emp.groupby("lista", sort=True):
        ag, idx = _agregado({"lista": lista}, g, fech, fim, cdi_aa)
        listas.append(ag)
        series[lista] = idx

    med = {s["setor"]: s for s in setores if s["lista"] == "Todas"}
    for k in ("pl", "pvp", "ev_ebitda"):
        emp[f"{k}_vs_setor"] = [multiplos.frente_ao_setor(v, med[s].get(f"{k}_mediana")) if el else None
                                for v, s, el in zip(emp[k], emp["setor"], emp["elegivel"])]

    mensal = {}
    for nome, idx in series.items():
        if len(idx):
            m = idx.resample("ME").last().dropna()
            mensal[nome] = {"meses": [d.strftime("%Y-%m") for d in m.index],
                            "base100": [round(float(x / idx.iloc[0] * 100), 2) for x in m]}

    def lista_dict(df):
        return [{k: _limpo(v) for k, v in linha.items()} for linha in df.to_dict("records")]

    return {"empresas": lista_dict(emp.astype(object).where(emp.notna(), None)),
            "setores": [{k: _limpo(v) for k, v in s.items()} for s in setores],
            "listas": [{k: _limpo(v) for k, v in s.items()} for s in listas],
            "series": mensal}
