import numpy as np
import pandas as pd
import pytest

from setores_b3 import metricas


def _serie(valores, inicio="2024-01-01"):
    return pd.Series(valores, index=pd.bdate_range(inicio, periods=len(valores)), dtype=float)


def test_retorno_acumulado_e_composto():
    assert metricas.retorno_acumulado(_serie([100, 110, 121])) == pytest.approx(0.21)


def test_anualizar_dois_anos():
    ini, fim = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-01-01")
    assert metricas.anualizar(0.21, ini, fim) == pytest.approx(0.10, abs=1e-3)


def test_drawdown_do_pico_ao_vale():
    # sobe a 120, cai a 90: queda de 25% a partir do pico
    assert metricas.max_drawdown(_serie([100, 120, 90, 110])) == pytest.approx(-0.25)


def test_volatilidade_anualiza_por_raiz_de_252():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, 2000)
    p = _serie(100 * np.cumprod(1 + r), "2015-01-01")
    assert metricas.volatilidade(p) == pytest.approx(0.01 * np.sqrt(252), rel=0.05)


def test_sharpe_usa_excesso_sobre_o_cdi():
    assert metricas.sharpe(0.20, 0.10, 0.25) == pytest.approx(0.4)
    assert np.isnan(metricas.sharpe(0.20, np.nan, 0.25))


def test_indice_igual_e_a_media_dos_retornos_diarios():
    p = pd.DataFrame({"A": [100, 110, 110], "B": [50, 50, 55]}, index=pd.bdate_range("2024-01-01", periods=3), dtype=float)
    idx = metricas.indice_igual(p)
    # dia 2: (10% + 0%)/2 = 5%; dia 3: (0% + 10%)/2 = 5%
    assert idx.iloc[-1] == pytest.approx(1.05 * 1.05)


def test_indice_igual_ignora_empresa_antes_do_primeiro_preco_e_repete_preco_sem_negocio():
    p = pd.DataFrame({"A": [100, 110, 121, 121], "B": [np.nan, np.nan, 50, 55]},
                     index=pd.bdate_range("2024-01-01", periods=4), dtype=float)
    idx = metricas.indice_igual(p)
    # dias 2 e 3 só com A (10% cada); dia 4: A 0% e B 10% -> 5%
    assert idx.iloc[-1] == pytest.approx(1.1 * 1.1 * 1.05)


def test_liquidez_mediana_e_presenca():
    idx = pd.bdate_range("2024-01-01", periods=100)
    f = pd.Series(10.0, index=idx)
    v = pd.Series([0, 1000] * 50, index=idx, dtype=float)
    l = metricas.liquidez(f, v)
    assert l["presenca_12m"] == pytest.approx(0.5)
    assert l["liq_mediana"] == pytest.approx(5000)


def test_resumo_marca_inicio_e_retorno_do_ano():
    idx = pd.bdate_range("2025-06-02", "2026-03-31")
    p = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
    r = metricas.resumo(p, pd.Timestamp("2026-03-31"), 0.10)
    assert r["desde"] == "2025-06-02"
    base = p[p.index <= pd.Timestamp("2025-12-31")].iloc[-1]
    assert r["ret_ano"] == pytest.approx(150 / base - 1)
    assert np.isnan(r["ret_12m"])  # menos de 12 meses de história
