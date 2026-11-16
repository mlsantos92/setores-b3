"""Coleta os dados, calcula o estudo e grava docs/dados.json, outputs/*.csv e o selo.

Uso:  python scripts/atualizar.py        (TESTES_OK=1|0 vem do workflow)
"""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from setores_b3 import calendario, coleta, cvm, estudo, metricas, selo, universo  # noqa: E402

CACHE_FUND = RAIZ / "data" / "processed" / "fundamentos.json"

esperado = calendario.ultimo_pregao_fechado()
fim = pd.Timestamp(esperado)
ajustes = universo.carregar_ajustes()
u = universo.aplicar_ajustes(universo.carregar(), ajustes)
todos = sorted({t for ts in u["tickers"] for t in ts})

tab = coleta.precos(todos + [coleta.IBOV])
fech, vol, bruto, prov = tab["ajustado"], tab["volume"], tab["bruto"], tab["proventos"]
ibov = fech.pop(coleta.IBOV) if coleta.IBOV in fech else pd.Series(dtype=float)
sem_dado = [t for t in todos if t not in fech.columns]
print(f"{len(todos)} códigos consultados, {len(sem_dado)} sem dado: {' '.join(sem_dado)}")

escolha = estudo.escolher_tickers(u, bruto[bruto.index <= fim], vol[vol.index <= fim], fech[fech.index <= fim])
escolhidos = [t for t in escolha["ticker"] if isinstance(t, str)]

# fundamentos: o que o Yahoo devolver hoje por cima do último valor guardado
guardado = json.loads(CACHE_FUND.read_text(encoding="utf-8")) if CACHE_FUND.exists() else {}
novos = coleta.fundamentos(escolhidos)
hoje = esperado.isoformat()
for t, d in novos.items():
    guardado[t] = {**d, "_em": hoje}
CACHE_FUND.parent.mkdir(parents=True, exist_ok=True)
CACHE_FUND.write_text(json.dumps(guardado, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
print(f"fundamentos: {len(novos)} novos de {len(escolhidos)} escolhidos")

# resultados oficiais (CVM): demonstrações protocoladas pelas empresas, só as métricas
HIST = RAIZ / "data" / "processed" / "historico_trimestral.json"
ANOS_HISTORICO = 6
oficiais, historico = {}, (json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else {})
cnpjs = {}
try:
    completo = os.environ.get("HIST_COMPLETO", "0") == "1" or not historico
    irmaos = {}
    for linha in escolha.itertuples():
        if isinstance(linha.ticker, str):
            irmaos[linha.ticker] = [t for t in list(linha.tickers) + list(linha.tickers_lista) if t != linha.ticker]
    cad = cvm.baixar_cadastro(esperado.year)
    cnpjs = cvm.cnpjs_dos_tickers(cad["fca_valor_mobiliario"], escolhidos, irmaos, ajustes["cnpj"])
    tab_cvm = {**cad, **cvm.baixar_demonstracoes(esperado.year, ANOS_HISTORICO if completo else 1, set(cnpjs.values()))}
    print("CVM:", "histórico completo" if completo else "ano corrente e anterior", {k: len(v) for k, v in tab_cvm.items()})
    oficiais = cvm.oficiais(tab_cvm, escolhidos, irmaos, ajustes["cnpj"])
    com_res = sum(1 for d in oficiais.values() if d.get("lucro_12m") is not None)
    print(f"CVM: {len(oficiais)} códigos no cadastro, {com_res} com lucro de 12 meses")
    print("CVM sem cadastro:", " ".join(t for t in escolhidos if t not in oficiais))
    print("CVM sem 12 meses:", " ".join(t for t, d in oficiais.items() if d.get("lucro_12m") is None))
    # histórico por trimestre, guardado por CNPJ: o que chega hoje entra por cima do que já havia
    for c, trimestres in cvm.historico(tab_cvm, {c: c for c in set(cnpjs.values())}).items():
        historico.setdefault(c, {}).update(trimestres)
    HIST.parent.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(historico, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    n_tri = sorted(len(v) for v in historico.values())
    print(f"Histórico: {len(historico)} empresas, mediana de {n_tri[len(n_tri) // 2] if n_tri else 0} trimestres")
    if "PETR4" in cnpjs:
        h = historico.get(cnpjs["PETR4"], {})
        print("Histórico PETR4:", {k: round(h[k]["lucro"] / 1e9, 1) for k in sorted(h)[-6:] if h[k].get("lucro") is not None})
except Exception as erro:
    print("CVM indisponível; múltiplos ficam com o Yahoo:", type(erro).__name__, erro)

# arquivo do painel: uma série por código, em R$ milhões, alinhada à lista de trimestres
rotulos = sorted({r for c in set(cnpjs.values()) for r in historico.get(c, {})})
serie = lambda h, k: [None if h.get(r, {}).get(k) is None else round(h[r][k] / 1e6, 1) for r in rotulos]  # noqa: E731
painel_hist = {"trimestres": rotulos, "unidade": "R$ milhões", "empresas": {
    t: {k: serie(historico[c], k) for k in ("receita", "ebit", "lucro", "pl")}
    for t, c in cnpjs.items() if c in historico}}
(RAIZ / "docs").mkdir(exist_ok=True)
(RAIZ / "docs" / "historico.json").write_text(json.dumps(painel_hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# CDI do período, para o Sharpe e a referência
cdi_aa, cdi_serie = float("nan"), pd.Series(dtype=float)
try:
    ini = fech.index.min().date()
    d = coleta.cdi_diario(ini, esperado + timedelta(days=1))
    d = d[d.index <= fim]
    cdi_serie = (1 + d / 100).cumprod()
    cdi_aa = metricas.anualizar(float(cdi_serie.iloc[-1] - 1), pd.Timestamp(ini), d.index[-1])
except Exception as erro:
    print("CDI indisponível:", type(erro).__name__, erro)

dados = estudo.montar(u, fech, vol, guardado, cdi_aa, fim, bruto=bruto, proventos=prov, oficiais=oficiais)

ref = {}
if len(ibov.dropna()):
    ib = ibov[ibov.index <= fim]
    ref["Ibovespa"] = {k: estudo._limpo(v) for k, v in metricas.resumo(ib, fim, cdi_aa).items()}
    m = ib.resample("ME").last().dropna()
    dados["series"]["Ibovespa"] = {"meses": [x.strftime("%Y-%m") for x in m.index],
                                   "base100": [round(float(v / ib.dropna().iloc[0] * 100), 2) for v in m]}
if len(cdi_serie):
    ref["CDI"] = {"ret_periodo": estudo._limpo(float(cdi_serie.iloc[-1] - 1)), "ret_aa": estudo._limpo(cdi_aa)}
    m = cdi_serie.resample("ME").last().dropna()
    dados["series"]["CDI"] = {"meses": [x.strftime("%Y-%m") for x in m.index],
                              "base100": [round(float(v * 100), 2) for v in m]}

info_selo = selo.avaliar(dados["empresas"], esperado, os.environ.get("TESTES_OK", "0") == "1")
dados["meta"] = {
    "selo": info_selo,
    "pregao": hoje,
    "inicio": fech.index.min().date().isoformat(),
    "cdi_aa": estudo._limpo(cdi_aa),
    "referencias": ref,
    "empresas": len(dados["empresas"]),
    "com_dado": sum(1 for e in dados["empresas"] if e["ticker"]),
    "elegiveis": sum(1 for e in dados["empresas"] if e["elegivel"]),
    "codigos_sem_dado": sem_dado,
    "base": {
        "elegiveis": sum(1 for e in dados["empresas"] if e["elegivel"]),
        "cvm": sum(1 for e in dados["empresas"] if e["elegivel"] and e.get("fonte") in ("CVM", "CVM e Yahoo")),
        "com_historico": sum(1 for e in dados["empresas"] if e["elegivel"] and e["ticker"] in painel_hist["empresas"]),
        "yahoo": sum(1 for e in dados["empresas"] if e["elegivel"] and e.get("fonte") == "Yahoo"),
        "divergentes": sum(1 for e in dados["empresas"] if e["elegivel"] and e.get("divergente")),
    },
    "fora_da_bolsa": ajustes["fora"],
    "criterio": {"liq_minima": estudo.LIQ_MINIMA, "presenca_minima": estudo.PRESENCA_MINIMA},
    "fonte": "CVM, dados abertos (DFP, ITR e FCA: resultados, capital e cadastro); Yahoo Finance (preços, valor de mercado, EV/EBITDA e conferência); Banco Central, SGS 12 (CDI)",
}

(RAIZ / "docs").mkdir(exist_ok=True)
(RAIZ / "docs" / "dados.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
(RAIZ / "outputs").mkdir(exist_ok=True)
pd.DataFrame(dados["empresas"]).to_csv(RAIZ / "outputs" / "empresas.csv", index=False, float_format="%.4f")
pd.DataFrame(dados["setores"]).to_csv(RAIZ / "outputs" / "setores.csv", index=False, float_format="%.4f")

print("Selo:", info_selo["cor"], "-", info_selo["motivo"])
print("Base dos múltiplos:", dados["meta"]["base"])
print(f"{dados['meta']['com_dado']} de {dados['meta']['empresas']} empresas com dado; {dados['meta']['elegiveis']} elegíveis")
