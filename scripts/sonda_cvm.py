"""Sonda: formato dos dados abertos da CVM (FCA, ITR, DFP)."""
import io, zipfile, requests, pandas as pd
B = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/"
def baixa(u):
    r = requests.get(B + u, timeout=180); print(u, r.status_code, len(r.content) // 1024, "KB"); r.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(r.content))
def le(z, nome, **k):
    return pd.read_csv(z.open(nome), sep=";", encoding="latin1", dtype=str, **k)
z = baixa("FCA/DADOS/fca_cia_aberta_2026.zip"); print(z.namelist())
for n in z.namelist():
    if "valor_mobiliario" in n or "geral" in n:
        d = le(z, n); print(n, list(d.columns)); print(d.head(3).to_string())
        if "valor_mobiliario" in n:
            c = [x for x in d.columns if "egocia" in x][0]
            print(d[d[c].isin(["PETR4", "ITUB4", "BBSE3", "SMTO3", "TAEE11", "SAUD3", "JBSS32"])].to_string())
for u in ["DFP/DADOS/dfp_cia_aberta_2026.zip", "DFP/DADOS/dfp_cia_aberta_2025.zip", "ITR/DADOS/itr_cia_aberta_2026.zip"]:
    try:
        z = baixa(u)
    except Exception as e:
        print("FALHOU", u, e); continue
    print(z.namelist())
    if "itr" in u:
        for parte in ["DRE_con", "BPP_con"]:
            d = le(z, f"itr_cia_aberta_{parte}_2026.csv"); print(parte, list(d.columns), len(d))
            print("DT_REFER:", d.DT_REFER.value_counts().to_dict())
            for cvm in ["009512", "019348", "023159", "020516"]:
                x = d[(d.CD_CVM == cvm) & (d.DT_REFER == d[d.CD_CVM == cvm].DT_REFER.max()) & (d.CD_CONTA.str.len() <= 7)]
                print(x.drop(columns=["CNPJ_CIA", "VERSAO", "GRUPO_DFP", "MOEDA", "ST_CONTA_FIXA"], errors="ignore").to_string())
