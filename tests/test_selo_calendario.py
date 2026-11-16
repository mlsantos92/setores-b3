from datetime import date, datetime

from setores_b3 import calendario, selo
from setores_b3.calendario import BRT


def test_pascoa_e_feriados_moveis():
    assert calendario.pascoa(2026) == date(2026, 4, 5)
    f = calendario.feriados(2026)
    assert date(2026, 2, 16) in f and date(2026, 2, 17) in f      # carnaval
    assert date(2026, 4, 3) in f                                   # sexta-feira santa
    assert date(2026, 6, 4) in f                                   # Corpus Christi


def test_ultimo_pregao_respeita_horario_fim_de_semana_e_feriado():
    assert calendario.ultimo_pregao_fechado(datetime(2026, 11, 16, 19, 0, tzinfo=BRT)) == date(2026, 11, 16)
    assert calendario.ultimo_pregao_fechado(datetime(2026, 11, 16, 13, 0, tzinfo=BRT)) == date(2026, 11, 13)
    # sábado 21/11: sexta 20/11 é feriado, então vale quinta 19/11
    assert calendario.ultimo_pregao_fechado(datetime(2026, 11, 21, 10, 0, tzinfo=BRT)) == date(2026, 11, 19)


def _emp(n_em_dia, n_atrasadas, fund=True):
    e = []
    for i in range(n_em_dia + n_atrasadas):
        e.append({"lista": "Large e Mid Caps", "ticker": f"T{i}", "elegivel": True,
                  "ultimo_preco_em": "2026-11-13" if i < n_em_dia else "2026-11-12",
                  "pvp": 1.0 if fund else None, "pl": None})
    return e


def test_selo_verde_amarelo_vermelho():
    esp = date(2026, 11, 13)
    assert selo.avaliar(_emp(98, 2), esp, True)["cor"] == "verde"
    assert selo.avaliar(_emp(80, 20), esp, True)["cor"] == "amarelo"
    assert selo.avaliar(_emp(100, 0, fund=False), esp, True)["cor"] == "amarelo"
    assert selo.avaliar(_emp(100, 0), esp, False)["cor"] == "vermelho"
    assert selo.avaliar([], esp, True)["cor"] == "vermelho"
