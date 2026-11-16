import numpy as np
import pandas as pd
import pytest

from setores_b3 import estudo, multiplos, universo


def _base():
    idx = pd.bdate_range("2021-11-16", "2026-11-13")
    n = len(idx)
    rng = np.random.default_rng(1)
    def caminho(mu):
        return 100 * np.cumprod(1 + rng.normal(mu, 0.015, n))
    fech = pd.DataFrame({"AAAA4": caminho(0.0005), "AAAA3": caminho(0.0005), "BBBB3": caminho(0.0002),
                         "CCCC3": caminho(0.0)}, index=idx)
    vol = pd.DataFrame({"AAAA4": 1e6, "AAAA3": 1e4, "BBBB3": 5e5, "CCCC3": 10.0}, index=idx)
    vol.loc[vol.index[::3], "CCCC3"] = 0  # micro cap que não negocia todo dia
    u = pd.DataFrame({
        "lista": ["Large e Mid Caps", "Large e Mid Caps", "Small e Micro Caps", "Small e Micro Caps"],
        "setor": ["Financeiro", "Financeiro", "Financeiro", "Saúde"],
        "subsetor": ["", "", "", ""],
        "empresa": ["Alfa", "Beta", "Gama", "Delta"],
        "tickers": [["AAAA4", "AAAA3"], ["BBBB3"], ["CCCC3"], ["ZZZZ3"]],
    })
    fund = {"AAAA4": {"trailingPE": 8.0, "priceToBook": 1.0, "trailingEps": 2.0},
            "BBBB3": {"trailingPE": 12.0, "priceToBook": 2.0, "trailingEps": 1.0}}
    return u, fech, vol, fund, idx[-1]


def test_escolhe_o_codigo_mais_liquido():
    u, fech, vol, _, _ = _base()
    e = estudo.escolher_tickers(u, fech, vol)
    assert e.loc[e.empresa == "Alfa", "ticker"].item() == "AAAA4"
    assert e.loc[e.empresa == "Delta", "ticker"].item() is None


def test_pouca_liquidez_fica_fora_dos_agregados():
    u, fech, vol, fund, fim = _base()
    d = estudo.montar(u, fech, vol, fund, 0.10, fim)
    emp = {e["empresa"]: e for e in d["empresas"]}
    assert emp["Gama"]["elegivel"] is False and emp["Alfa"]["elegivel"] is True
    fin = next(s for s in d["setores"] if s["setor"] == "Financeiro" and s["lista"] == "Todas")
    assert fin["empresas"] == 3 and fin["elegiveis"] == 2


def test_mediana_do_setor_e_posicao_relativa():
    u, fech, vol, fund, fim = _base()
    d = estudo.montar(u, fech, vol, fund, 0.10, fim)
    fin = next(s for s in d["setores"] if s["setor"] == "Financeiro" and s["lista"] == "Todas")
    assert fin["pl_mediana"] == pytest.approx(10.0)
    alfa = next(e for e in d["empresas"] if e["empresa"] == "Alfa")
    assert alfa["pl_vs_setor"] == pytest.approx(-0.2)


def test_dividend_yield_soma_proventos_de_12_meses_sobre_o_preco_negociado():
    u, fech, vol, fund, fim = _base()
    bruto = fech * 0 + 50.0
    prov = fech * 0
    prov.loc[prov.index[-10], "AAAA4"] = 1.5
    prov.loc[prov.index[-200], "AAAA4"] = 1.5
    prov.loc[prov.index[-400], "AAAA4"] = 9.0   # há mais de 12 meses: não conta
    d = estudo.montar(u, fech, vol, fund, 0.10, fim, bruto=bruto, proventos=prov)
    alfa = next(e for e in d["empresas"] if e["empresa"] == "Alfa")
    assert alfa["dy"] == pytest.approx(3.0 / 50.0)


def test_salto_de_um_dia_marca_suspeito_e_tira_dos_agregados():
    u, fech, vol, fund, fim = _base()
    fech.loc[fech.index[500]:, "BBBB3"] *= 150   # grupamento não ajustado
    d = estudo.montar(u, fech, vol, fund, 0.10, fim)
    beta = next(e for e in d["empresas"] if e["empresa"] == "Beta")
    assert beta["suspeito"] is True and beta["elegivel"] is False


def test_mediana_ignora_vazio_e_nan():
    assert multiplos.mediana([None, float("nan"), 4.0, 2.0, 9.0]) == pytest.approx(4.0)
    assert multiplos.mediana([None, float("nan")]) is None


def test_precos_depois_do_pregao_esperado_sao_ignorados():
    u, fech, vol, fund, fim = _base()
    corte = fech.index[-3]
    d = estudo.montar(u, fech, vol, fund, 0.10, corte)
    assert all(e["ultimo_preco_em"] <= corte.date().isoformat() for e in d["empresas"] if e["ticker"])


def test_saida_nao_tem_nan():
    import json
    u, fech, vol, fund, fim = _base()
    json.dumps(estudo.montar(u, fech, vol, fund, float("nan"), fim), allow_nan=False)


def test_limpar_trata_prejuizo_e_valores_absurdos():
    m = multiplos.limpar({"trailingPE": -5.0, "trailingEps": -1.0, "priceToBook": 500,
                          "returnOnEquity": 0.15, "debtToEquity": 80.0})
    assert m["pl"] is None and m["prejuizo"] is True
    assert m["pvp"] is None
    assert multiplos.dividend_yield(95.0, 100.0) is None and multiplos.dividend_yield(6.0, 100.0) == pytest.approx(0.06)
    assert m["roe"] == pytest.approx(0.15) and m["div_pl"] == pytest.approx(0.8)


def test_ajustes_trocam_codigo_sem_repetir():
    u = pd.DataFrame({"empresa": ["X"], "tickers": [["ELET3", "ELET6", "AXIA3"]]})
    out = universo.aplicar_ajustes(u, {"renomear": {"ELET3": "AXIA3", "ELET6": "AXIA6"}, "fora": {}})
    assert out.tickers.iloc[0] == ["AXIA3", "AXIA6"]
    assert out.tickers_lista.iloc[0] == ["ELET3", "ELET6", "AXIA3"]


def test_universo_do_arquivo():
    u = universo.carregar()
    assert len(u) == 282
    assert set(u.lista) == {"Large e Mid Caps", "Small e Micro Caps"}
    assert u.setor.nunique() == 11


def test_codigo_so_com_preco_depois_do_corte_fica_sem_dado():
    u, fech, vol, fund, fim = _base()
    fech["NOVA3"] = np.nan
    fech.loc[fech.index[-1], "NOVA3"] = 10.0
    vol["NOVA3"] = 100.0
    u.loc[u.empresa == "Delta", "tickers"] = pd.Series([["NOVA3"]], index=u.index[u.empresa == "Delta"])
    d = estudo.montar(u, fech, vol, fund, 0.10, fech.index[-2])
    delta = next(e for e in d["empresas"] if e["empresa"] == "Delta")
    assert delta["ticker"] is None


def test_resultado_oficial_substitui_o_yahoo_e_marca_divergencia():
    u, fech, vol, fund, fim = _base()
    fund["AAAA4"]["marketCap"] = 1_000.0
    of = {"AAAA4": {"lucro_12m": 100.0, "patrimonio": 500.0, "receita_12m": 400.0, "resultado_ate": "2026-09-30",
                    "documento": "ITR", "auditor": "KPMG Auditores Independentes", "big4": "KPMG"}}
    d = estudo.montar(u, fech, vol, fund, 0.10, fim, oficiais=of)
    alfa = next(e for e in d["empresas"] if e["empresa"] == "Alfa")
    beta = next(e for e in d["empresas"] if e["empresa"] == "Beta")
    assert alfa["fonte"] == "CVM" and alfa["big4"] == "KPMG"
    assert alfa["pl"] == pytest.approx(10.0) and alfa["pvp"] == pytest.approx(2.0)
    assert alfa["roe"] == pytest.approx(0.2) and alfa["margem"] == pytest.approx(0.25)
    assert alfa["pl_yahoo"] == pytest.approx(8.0)
    assert alfa["divergente"] is True            # P/VP 2,0 na CVM contra 1,0 no Yahoo
    assert beta["fonte"] == "Yahoo" and beta["pl"] == pytest.approx(12.0)


def test_prejuizo_oficial_tira_o_pl():
    r = multiplos.de_resultado(1000.0, -50.0, 400.0)
    assert r["prejuizo"] is True and r["pl"] is None and r["pvp"] == pytest.approx(2.5)


def test_valor_de_mercado_soma_classes_trata_unit_e_escala():
    idx = pd.bdate_range("2026-11-09", periods=3)
    precos = pd.DataFrame({"XPTO3": [10.0] * 3, "XPTO4": [12.0] * 3, "XPTO11": [34.0] * 3, "SOLO3": [5.0] * 3}, index=idx)
    of = {"acoes_on": 100.0, "acoes_pn": 200.0}
    certo = 100 * 10 + 200 * 12
    assert estudo.valor_de_mercado(of, "XPTO4", precos, 3500.0) == pytest.approx(certo)
    # unit sem composição informada: basta ter o preço das duas classes
    assert estudo.valor_de_mercado(of, "XPTO11", precos, 10_000.0) == pytest.approx(certo)
    # sem preço das classes: preço da unit dividido pelas 3 ações que ela representa
    so_unit = precos[["XPTO11"]]
    assert estudo.valor_de_mercado({**of, "unit": (1.0, 2.0)}, "XPTO11", so_unit, 4000.0) == pytest.approx(300 * 34 / 3)
    assert estudo.valor_de_mercado(of, "XPTO11", so_unit, 3000.0) is None
    # quantidade informada em milhares: a referência decide a escala
    assert estudo.valor_de_mercado(of, "XPTO4", precos, 3_300_000.0) == pytest.approx(certo * 1000)
    # nenhuma escala chega perto da referência: fica sem valor (vale a outra fonte)
    assert estudo.valor_de_mercado(of, "XPTO4", precos, 90_000.0) is None
    # sem referência, decide o patrimônio líquido; sem os dois, nada
    assert estudo.valor_de_mercado({**of, "patrimonio": 2_000_000.0}, "XPTO4", precos, None) == pytest.approx(certo * 1000)
    assert estudo.valor_de_mercado(of, "XPTO4", precos, None) is None
    assert estudo.valor_de_mercado({}, "SOLO3", precos, 100.0) is None


def test_unit_sem_resultado_oficial_fica_sem_pl_do_yahoo():
    u, fech, vol, fund, fim = _base()
    for df in (fech, vol):
        df["BBBB11"] = df["BBBB3"]
    u.loc[u.empresa == "Beta", "tickers"] = pd.Series([["BBBB11"]], index=u.index[u.empresa == "Beta"])
    fund["BBBB11"] = {"trailingPE": 86.0, "priceToBook": 3.0, "trailingEps": 1.0}
    d = estudo.montar(u, fech, vol, fund, 0.10, fim)
    beta = next(e for e in d["empresas"] if e["empresa"] == "Beta")
    assert beta["pl"] is None and beta["pvp"] == pytest.approx(3.0) and beta["fonte"] == "Yahoo"
