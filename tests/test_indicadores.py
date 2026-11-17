import pytest

from setores_b3 import indicadores as ind


def _hist():
    """Seis anos de trimestres iguais (receita 100, bruto 40, EBIT 20, EBITDA 30, lucro 10), crescendo 10% ao ano."""
    h = {}
    for ano in range(2020, 2027):
        f = 1.1 ** (ano - 2020)
        for q in (1, 2, 3, 4):
            h[f"{ano}T{q}"] = {"receita": 100 * f, "bruto": 40 * f, "ebit": 20 * f, "ebitda": 30 * f, "lucro": 10 * f}
    h.pop("2026T4")
    h["2026T3"].update({"pl": 400.0, "passivo": 600.0, "divida": 300.0, "caixa": 100.0, "ativo": 1000.0,
                        "ativo_circ": 350.0, "passivo_circ": 250.0})
    return h


def test_doze_meses_soma_quatro_trimestres_e_exige_todos():
    h = _hist()
    assert ind.doze_meses(h, "2026T3", "receita") == pytest.approx(100 * 1.1 ** 6 * 3 + 100 * 1.1 ** 5)
    del h["2026T1"]
    assert ind.doze_meses(h, "2026T3", "receita") is None


def test_indicadores_principais():
    h = _hist()
    f6, f5 = 1.1 ** 6, 1.1 ** 5
    rec = 100 * (3 * f6 + f5)
    luc, ebitda, ebit = rec / 10, rec * 0.3, rec * 0.2
    r = ind.calcular(h, valor_mercado=800.0, preco=8.0, dy=0.05)
    assert r["ind_ate"] == "2026T3"
    assert r["pl"] == pytest.approx(800 / luc)
    assert r["pvp"] == pytest.approx(2.0)
    assert r["vpa"] == pytest.approx(4.0)                 # 400 ÷ 100 ações (800 ÷ 8)
    assert r["lpa"] == pytest.approx(luc / 100)
    assert r["ev_ebitda"] == pytest.approx((800 + 200) / ebitda)
    assert r["dl_ebitda"] == pytest.approx(200 / ebitda)
    assert r["dl_pl"] == pytest.approx(0.5)
    assert r["liq_corrente"] == pytest.approx(1.4)
    assert r["p_capgiro"] == pytest.approx(8.0)          # 800 ÷ (350 − 250)
    assert r["p_acl"] == pytest.approx(800 / (350 - 1000))  # ativo circ. − passivo total: negativo, como nos sites de referência
    assert r["passivos_ativos"] == pytest.approx(0.6) and r["pl_ativos"] == pytest.approx(0.4)
    assert r["m_bruta"] == pytest.approx(0.4) and r["m_ebitda"] == pytest.approx(0.3) and r["m_liquida"] == pytest.approx(0.1)
    assert r["roe"] == pytest.approx(luc / 400) and r["roa"] == pytest.approx(luc / 1000)
    assert r["roic"] == pytest.approx(ebit * 0.66 / (400 + 200))
    h["2026T3"]["caixa"] = 500.0                             # caixa líquido: capital investido = só o patrimônio
    assert ind.calcular(h, 800.0, 8.0)["roic"] == pytest.approx(ebit * 0.66 / 400)
    assert r["giro_ativos"] == pytest.approx(rec / 1000)
    assert r["cagr_receita"] == pytest.approx(0.10, abs=1e-9) and r["cagr_lucro"] == pytest.approx(0.10, abs=1e-9)  # 2025 contra 2020
    assert r["peg"] == pytest.approx(r["pl"] / 10)
    assert r["dy"] == pytest.approx(0.05)


def test_prejuizo_tira_pl_e_cagr_mas_mantem_o_resto():
    h = _hist()
    for q in ("2025T1", "2025T2", "2025T3", "2025T4", "2026T1", "2026T2", "2026T3"):
        h[q]["lucro"] = -5.0
    r = ind.calcular(h, 800.0, 8.0)
    assert r["pl"] is None and r["cagr_lucro"] is None and r["peg"] is None
    assert r["roe"] == pytest.approx(-20 / 400)              # ROE negativo é informativo e fica
    assert r["prejuizo_12m"] is True and r["m_liquida"] < 0 and r["pvp"] == pytest.approx(2.0)


def test_sem_balanco_no_trimestre_usa_o_anterior_completo_ou_nada():
    h = _hist()
    del h["2026T3"]["pl"]
    assert ind.calcular(h, 800.0, 8.0) == {}
    h["2026T2"]["pl"] = 500.0
    assert ind.calcular(h, 800.0, 8.0)["ind_ate"] == "2026T2"


def test_razao_e_denominador_negativo():
    assert ind.razao(10, -2) is None and ind.razao(10, -2, negativo=True) == -5
    assert ind.razao(None, 2) is None and ind.razao(1, 0) is None
