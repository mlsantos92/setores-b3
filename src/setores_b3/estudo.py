"""Monta o estudo: escolhe o código mais líquido de cada empresa, calcula as métricas
por empresa e agrega por setor e por lista (large/mid × small/micro)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import indicadores, metricas, multiplos

LIQ_MINIMA = 100_000      # R$/dia, mediana dos últimos 60 pregões
PRESENCA_MINIMA = 0.90    # fração dos pregões dos últimos 12 meses com negócio
INDICADORES = list(dict.fromkeys(["pl", "pvp", "ev_ebitda", "dy", "roe", "margem", "div_pl"] + indicadores.TODOS))


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


def valor_de_mercado(of: dict, ticker: str, precos: pd.DataFrame, referencia: float | None = None) -> float | None:
    """Valor de mercado pelas ações informadas à CVM: ON × preço da ON + PN × preço da PN.

    - Classe sem preço (ou com preço de papel quase sem negócio, que destoa muito) usa o preço
      por ação do código escolhido; em unit, o preço da unit dividido pelas ações que ela representa.
    - A CVM não diz se a quantidade de ações está em unidades ou em milhares. ``referencia``
      (o valor de mercado de outra fonte) decide a escala; se nenhuma escala chega perto, a
      função devolve None e vale a outra fonte. Sem referência, decide o patrimônio líquido.
    """
    on, pn = of.get("acoes_on"), of.get("acoes_pn")
    if on is None or pn is None or ticker not in precos.columns:
        return None

    def ultimo(t):
        if t in precos.columns:
            x = precos[t].dropna()
            return float(x.iloc[-1]) if len(x) else None
        return None

    unit = ticker.endswith("11")
    ref = ultimo(ticker)
    if unit:
        n_on, n_pn = of.get("unit") or (0, 0)
        ref = ref / (n_on + n_pn) if ref and n_on + n_pn > 0 else None
    raiz = ticker[:4]

    def classe(codigos):
        for t in codigos:
            x = ultimo(t)
            if x and (ref is None or 1 / 3 < x / ref < 3):
                return x
        return ref

    p_on, p_pn = classe([raiz + "3"]), classe([raiz + "4", raiz + "5", raiz + "6"])
    if (on > 0 and not p_on) or (pn > 0 and not p_pn):
        return None
    bruto = on * (p_on or 0.0) + pn * (p_pn or 0.0)
    if referencia:
        # em unit a outra fonte costuma exagerar (preço da unit × todas as ações); em ação comum
        # uma diferença grande indica classes com direitos econômicos diferentes: vale a outra fonte
        lo, hi = (1 / 8, 1.5) if unit else (1 / 2.5, 2.5)
        return next((bruto * k for k in (1.0, 1000.0) if lo < bruto * k / referencia < hi), None)
    pl = of.get("patrimonio")
    if pl and pl > 0:
        # sem referência: fica a escala que deixa o preço sobre o patrimônio mais perto de 1
        k = min((1.0, 1000.0), key=lambda k: abs(np.log(bruto * k / pl)))
        return bruto * k if 0.05 < bruto * k / pl < 30 else None
    return None


ATRASO_MAXIMO = 270   # dias entre a data-base do último resultado e o pregão


def _base_oficial(m: dict, of: dict, fim: pd.Timestamp | None = None) -> dict:
    """Troca os múltiplos do Yahoo pelos calculados das demonstrações da CVM, guardando a conferência.

    Empresa que não protocola resultado há mais de ``ATRASO_MAXIMO`` dias fica sem P/L, P/VP,
    ROE e margem: nenhum número de 12 meses dela seria atual.
    """
    extra = {"fonte": "Yahoo" if any(m.get(k) is not None for k in ("pl", "pvp", "roe")) else None,
             "pl_yahoo": m.get("pl"), "pvp_yahoo": m.get("pvp"), "divergente": False,
             "resultado_ate": of.get("resultado_ate"), "documento": of.get("documento"),
             "auditor": of.get("auditor"),
             "site": of.get("site"), "lucro_12m": of.get("lucro_12m"), "patrimonio": of.get("patrimonio")}
    extra["atrasado"] = bool(fim is not None and of.get("resultado_ate")
                             and (fim - pd.Timestamp(of["resultado_ate"])).days > ATRASO_MAXIMO)
    if extra["atrasado"]:
        return {**extra, "fonte": None, "pl": None, "pvp": None, "roe": None, "margem": None}
    if of.get("_unit_sem_cvm"):
        extra["pl"] = None
    calc = multiplos.de_resultado(m.get("valor_mercado"), of.get("lucro_12m"), of.get("patrimonio"), of.get("receita_12m"))
    if not calc or m.get("valor_mercado") is None:
        return extra
    completo = of.get("lucro_12m") is not None and of.get("patrimonio") is not None
    extra["fonte"] = "CVM" if completo else "CVM e Yahoo"
    extra["divergente"] = multiplos.diverge(calc.get("pl"), m.get("pl")) or multiplos.diverge(calc.get("pvp"), m.get("pvp"))
    return {**extra, **calc}


def _agregado(nome: dict, emp: pd.DataFrame, fech: pd.DataFrame, fim: pd.Timestamp, cdi_aa: float) -> dict:
    eleg = emp[emp["elegivel"]]
    indice = metricas.indice_igual(fech[list(eleg["ticker"])]) if len(eleg) else pd.Series(dtype=float)
    r = metricas.resumo(indice, fim, cdi_aa) if len(indice) else {}
    meds = {f"{k}_mediana": multiplos.mediana(list(eleg[k])) for k in INDICADORES}
    return {**nome, "empresas": int(len(emp)), "elegiveis": int(len(eleg)),
            "com_prejuizo": int(eleg["prejuizo"].sum()) if len(eleg) else 0, **r, **meds}, indice


def montar(universo: pd.DataFrame, fech: pd.DataFrame, vol: pd.DataFrame, fundamentos: dict,
           cdi_aa: float, fim: pd.Timestamp, bruto: pd.DataFrame | None = None,
           proventos: pd.DataFrame | None = None, oficiais: dict | None = None,
           historico: dict | None = None, proventos_b3: dict | None = None) -> dict:
    """Devolve {"empresas": [...], "setores": [...], "listas": [...], "series": {...}}.

    ``fech`` é o preço ajustado por proventos. ``bruto`` (preço negociado) e ``proventos``
    são opcionais: sem eles a liquidez usa o preço ajustado e não há dividend yield.
    ``oficiais`` traz, por código, o resultado protocolado na CVM e o auditor: quando existe,
    P/L, P/VP, ROE e margem saem dele e os números do Yahoo ficam só como conferência.
    ``historico`` traz, por código, os trimestres da CVM; com ele a empresa ganha o conjunto
    completo de indicadores (``indicadores.calcular``), que passa a valer no lugar dos anteriores.
    """
    oficiais = oficiais or {}
    historico = historico or {}
    proventos_b3 = proventos_b3 or {}
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
            reg.append({**base, **{k: None for k in INDICADORES}, "prejuizo": False, "valor_mercado": None,
                        "fonte": None, "divergente": False, "auditor": None})
            continue
        r = metricas.resumo(fech[e.ticker], fim, cdi_aa)
        m = multiplos.limpar(fundamentos.get(e.ticker, {}))
        of = dict(oficiais.get(e.ticker, {}))
        if e.ticker.endswith("11") and of.get("lucro_12m") is None:
            of["_unit_sem_cvm"] = True   # o P/L do Yahoo para unit compara o preço da unit com o lucro por ação
        vm = valor_de_mercado(of, e.ticker, bruto, m.get("valor_mercado"))
        m["valor_mercado_fonte"] = "Yahoo" if m.get("valor_mercado") is not None else None
        if vm:
            m["valor_mercado"], m["valor_mercado_fonte"] = vm, "CVM"
        m.update(_base_oficial(m, of, fim))
        m["dy"], m["dy_fonte"] = None, None
        preco_atual = float(bruto[e.ticker].dropna().iloc[-1])
        if e.ticker in proventos_b3:
            ini_12m = (fim - pd.DateOffset(years=1)).date().isoformat()
            pago = sum(v for d, v in proventos_b3[e.ticker] if ini_12m < d <= fim.date().isoformat())
            m["dy"], m["dy_fonte"] = multiplos.dividend_yield(pago, preco_atual), "B3"
        elif proventos is not None and e.ticker in proventos.columns:
            m["dy_fonte"] = "Yahoo"
            pago = proventos[e.ticker]
            pago = pago[(pago.index > fim - pd.DateOffset(years=1)) & (pago.index <= fim)].sum()
            m["dy"] = multiplos.dividend_yield(float(pago), float(bruto[e.ticker].dropna().iloc[-1]))
        hist = historico.get(e.ticker)
        if hist and not m.get("atrasado"):
            ind = indicadores.calcular(hist, m.get("valor_mercado"), float(bruto[e.ticker].dropna().iloc[-1]), m["dy"])
            if ind:
                q = ind["ind_ate"]
                fim_q = pd.Timestamp(year=int(q[:4]), month=int(q[5:]) * 3, day=1) + pd.offsets.MonthEnd(0)
                if (fim - fim_q).days <= ATRASO_MAXIMO:
                    m.update({k: ind[k] for k in indicadores.TODOS})
                    m.update({"ind_ate": q, "margem": ind["m_liquida"], "prejuizo": ind["prejuizo_12m"],
                              "fonte": "CVM", "div_pl": ind["dl_pl"]})
        reg.append({**base, **{k: None for k in indicadores.TODOS}, **r, **m,
                    "ultimo_preco_em": fech[e.ticker].dropna().index[-1].date().isoformat()})
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
