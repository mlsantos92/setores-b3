from setores_b3 import coleta


def test_proventos_b3_filtra_classe_e_descarta_repetidos(monkeypatch):
    linhas = [
        {"isinCode": "BRXPTOACNOR0", "lastDatePrior": "19/12/2025", "paymentDate": "12/08/2026", "rate": "0,41283167300", "label": "DIVIDENDO"},
        {"isinCode": "BRXPTOACNOR0", "lastDatePrior": "19/12/2025", "paymentDate": "11/08/2027", "rate": "0,41283167300", "label": "DIVIDENDO"},
        {"isinCode": "BRXPTOACNOR0", "lastDatePrior": "19/12/2025", "paymentDate": "11/08/2027", "rate": "0,41283167300", "label": "DIVIDENDO"},
        {"isinCode": "BRXPTOACNPR7", "lastDatePrior": "20/03/2026", "paymentDate": "10/03/2027", "rate": "1.234,5", "label": "JRS CAP PROPRIO"},
        {"isinCode": "BRXPTOCDAM10", "lastDatePrior": "20/03/2026", "paymentDate": "10/03/2027", "rate": "0,9", "label": "DIVIDENDO"},
    ]
    monkeypatch.setattr(coleta, "_b3_emissor", lambda e: linhas if e == "XPTO" else None)
    monkeypatch.setattr(coleta.time, "sleep", lambda s: None)
    r = coleta.proventos_b3(["XPTO3", "XPTO4", "XPTO11", "NADA3", "JBSS32"])
    assert r["XPTO3"] == [("2025-12-19", 0.412831673), ("2025-12-19", 0.412831673)]   # duas parcelas, a repetida sai
    assert r["XPTO4"] == [("2026-03-20", 1234.5)] and r["XPTO11"] == [("2026-03-20", 0.9)]
    assert "NADA3" not in r and "JBSS32" not in r
