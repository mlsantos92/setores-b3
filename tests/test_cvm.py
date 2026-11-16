import pandas as pd
import pytest

from setores_b3 import cvm

C = "11.111.111/0001-11"


def _l(tipo, ref, ordem, ini, fim, cd, ds, valor, versao="1", escala="MIL"):
    return {"CNPJ_CIA": C, "DT_REFER": ref, "VERSAO": versao, "ESCALA_MOEDA": escala, "ORDEM_EXERC": ordem,
            "DT_INI_EXERC": ini, "DT_FIM_EXERC": fim, "CD_CONTA": cd, "DS_CONTA": ds, "VL_CONTA": str(valor), "TIPO": tipo}


def _dre():
    L = "Lucro/Prejuízo Consolidado do Período"
    A = "Atribuído a Sócios da Empresa Controladora"
    linhas = []
    # DFP 2025: receita 1.000, lucro 100 (90 da controladora)
    linhas += [_l("DFP", "2025-12-31", "ÚLTIMO", "2025-01-01", "2025-12-31", "3.01", "Receita de Venda", 1000),
               _l("DFP", "2025-12-31", "ÚLTIMO", "2025-01-01", "2025-12-31", "3.11", L, 100),
               _l("DFP", "2025-12-31", "ÚLTIMO", "2025-01-01", "2025-12-31", "3.11.01", A, 90)]
    # ITR 3T26: acumulado 9 meses e o trimestre isolado, exercício atual e anterior
    for ordem, ano, rec9, luc9, ctrl9 in (("ÚLTIMO", "2026", 900, 120, 108), ("PENÚLTIMO", "2025", 700, 70, 63)):
        linhas += [_l("ITR", "2026-09-30", ordem, f"{ano}-01-01", f"{ano}-09-30", "3.01", "Receita de Venda", rec9),
                   _l("ITR", "2026-09-30", ordem, f"{ano}-07-01", f"{ano}-09-30", "3.01", "Receita de Venda", 300),
                   _l("ITR", "2026-09-30", ordem, f"{ano}-01-01", f"{ano}-09-30", "3.11", L, luc9),
                   _l("ITR", "2026-09-30", ordem, f"{ano}-07-01", f"{ano}-09-30", "3.11", L, 40),
                   _l("ITR", "2026-09-30", ordem, f"{ano}-01-01", f"{ano}-09-30", "3.11.01", A, ctrl9)]
    return pd.DataFrame(linhas)


def _bpp():
    b = lambda cd, ds, v, ordem="ÚLTIMO": {"CNPJ_CIA": C, "DT_REFER": "2026-09-30", "VERSAO": "1", "ESCALA_MOEDA": "MIL",
                                           "ORDEM_EXERC": ordem, "DT_FIM_EXERC": "2026-09-30", "CD_CONTA": cd,
                                           "DS_CONTA": ds, "VL_CONTA": str(v), "TIPO": "ITR"}
    return pd.DataFrame([b("2.03", "Patrimônio Líquido Consolidado", 800),
                         b("2.03.09", "Participação dos Acionistas Não Controladores", 50),
                         b("2.03", "Patrimônio Líquido Consolidado", 700, "PENÚLTIMO")])


def test_ultimos_12_meses_somam_anual_mais_acumulado_menos_mesmo_periodo_anterior():
    r = cvm.resultado_empresa(cvm._preparar(_dre()), cvm._preparar(_bpp()))
    assert r["documento"] == "ITR" and r["resultado_ate"] == "2026-09-30"
    assert r["lucro_12m"] == pytest.approx((90 + 108 - 63) * 1000)       # lucro da controladora, em reais
    assert r["receita_12m"] == pytest.approx((1000 + 900 - 700) * 1000)
    assert r["patrimonio"] == pytest.approx((800 - 50) * 1000)           # sem os minoritários


def test_versao_reapresentada_substitui_a_original():
    d = _dre()
    novo = d[(d.TIPO == "ITR") & (d.CD_CONTA == "3.11.01") & (d.ORDEM_EXERC == "ÚLTIMO")].assign(VERSAO="2", VL_CONTA="118")
    outras = d[d.TIPO == "ITR"].assign(VERSAO="2")
    outras = outras[~((outras.CD_CONTA == "3.11.01") & (outras.ORDEM_EXERC == "ÚLTIMO"))]
    r = cvm.resultado_empresa(cvm._preparar(pd.concat([d, outras, novo])), cvm._preparar(_bpp()))
    assert r["lucro_12m"] == pytest.approx((90 + 118 - 63) * 1000)


def test_sem_dfp_do_ano_anterior_nao_inventa_12_meses():
    d = _dre()
    r = cvm.resultado_empresa(cvm._preparar(d[d.TIPO == "ITR"]), cvm._preparar(_bpp()))
    assert r["lucro_12m"] is None and r["patrimonio"] == pytest.approx(750_000)


def test_dfp_mais_recente_vale_o_ano_cheio():
    d = _dre()
    r = cvm.resultado_empresa(cvm._preparar(d[d.TIPO == "DFP"]), pd.DataFrame())
    assert r["documento"] == "DFP" and r["lucro_12m"] == pytest.approx(90_000)


def test_big4_reconhece_as_quatro_e_recusa_as_outras():
    assert cvm.big4("PricewaterhouseCoopers Auditores Independentes Ltda.") == "PwC"
    assert cvm.big4("ERNST & YOUNG AUDITORES INDEPENDENTES S/S LTDA") == "EY"
    assert cvm.big4("KPMG Auditores Independentes Ltda.") == "KPMG"
    assert cvm.big4("Deloitte Touche Tohmatsu Auditores Independentes Ltda.") == "Deloitte"
    assert cvm.big4("Grant Thornton Auditores Independentes Ltda.") is None
    assert cvm.big4("BDO RCS Auditores Independentes") is None


def test_mapa_de_codigos_fica_com_o_cadastro_mais_recente():
    vm = pd.DataFrame({"CNPJ_Companhia": ["A", "B"], "Data_Referencia": ["2025-01-01", "2026-01-01"],
                       "Versao": ["1", "1"], "Codigo_Negociacao": ["XPTO3", "XPTO3"]})
    assert cvm.mapa_tickers(vm) == {"XPTO3": "B"}


def test_empresa_sem_linha_de_controladora_ou_minoritarios_usa_o_total():
    d = _dre()
    d = d[d.CD_CONTA != "3.11.01"]
    b = _bpp()
    b = b[b.CD_CONTA != "2.03.09"]
    r = cvm.resultado_empresa(cvm._preparar(d), cvm._preparar(b))
    assert r["lucro_12m"] == pytest.approx((100 + 120 - 70) * 1000)
    assert r["patrimonio"] == pytest.approx(800_000)


def test_oficiais_junta_resultado_auditor_e_site():
    tab = {"dre_con": _dre(), "bpp_con": _bpp(), "dre_ind": pd.DataFrame(), "bpp_ind": pd.DataFrame(),
           "fca_valor_mobiliario": pd.DataFrame({"CNPJ_Companhia": [C], "Data_Referencia": ["2026-01-01"], "Versao": ["1"],
                                                 "Codigo_Negociacao": ["XPTO3"]}),
           "fca_geral": pd.DataFrame({"CNPJ_Companhia": [C], "Data_Referencia": ["2026-01-01"], "Versao": ["1"],
                                      "Pagina_Web": ["ri.xpto.com.br"]}),
           "fca_auditor": pd.DataFrame({"CNPJ_Companhia": [C, C], "Data_Referencia": ["2026-01-01"] * 2, "Versao": ["1"] * 2,
                                        "Auditor": ["BDO RCS Auditores", "KPMG Auditores Independentes Ltda."],
                                        "Data_Inicio_Atuacao_Auditor": ["2019-01-01", "2024-01-01"],
                                        "Data_Fim_Atuacao_Auditor": ["2023-12-31", None]})}
    o = cvm.oficiais(tab, ["XPTO3", "NADA3"])
    assert set(o) == {"XPTO3"}
    assert o["XPTO3"]["big4"] == "KPMG" and o["XPTO3"]["site"] == "https://ri.xpto.com.br"
    assert o["XPTO3"]["lucro_12m"] == pytest.approx(135_000) and o["XPTO3"]["visao"] == "consolidado"


def test_capital_desconta_tesouraria_e_unit_le_a_composicao():
    cap = pd.DataFrame({"CNPJ_CIA": [C], "DT_REFER": ["2026-09-30"], "VERSAO": ["1"],
                        "QT_ACAO_ORDIN_CAP_INTEGR": ["1000"], "QT_ACAO_PREF_CAP_INTEGR": ["2000"],
                        "QT_ACAO_TOTAL_CAP_INTEGR": ["3000"], "QT_ACAO_ORDIN_TESOURO": ["100"],
                        "QT_ACAO_PREF_TESOURO": ["0"], "QT_ACAO_TOTAL_TESOURO": ["100"]})
    assert cvm.capital(cap)[C] == {"acoes_on": 900.0, "acoes_pn": 2000.0}
    vm = pd.DataFrame({"CNPJ_Companhia": [C, C], "Data_Referencia": ["2026-01-01"] * 2, "Versao": ["1"] * 2,
                       "Codigo_Negociacao": ["TAEE11", "KLBN11"], "Composicao_BDR_Unit": ["1 ON / 2 PN", "1 ação ordinária e 4 ações preferenciais"]})
    u = cvm.composicao_units(vm)
    assert u["TAEE11"] == (1.0, 2.0) and u["KLBN11"] == (1.0, 4.0)


def test_cadastro_achado_pelo_codigo_irmao():
    tab = {"dre_con": _dre(), "bpp_con": _bpp(), "fca_valor_mobiliario": pd.DataFrame(
        {"CNPJ_Companhia": [C], "Data_Referencia": ["2026-01-01"], "Versao": ["1"], "Codigo_Negociacao": ["XPTO3"]})}
    o = cvm.oficiais(tab, ["XPTO11"], {"XPTO11": ["XPTO3", "XPTO4"]})
    assert o["XPTO11"]["lucro_12m"] == pytest.approx(135_000)
