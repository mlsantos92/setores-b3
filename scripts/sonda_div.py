import base64, json, requests
H = {"User-Agent": "Mozilla/5.0"}
for cod in ("WEGE", "MDNE", "POMO", "PETR", "TAEE"):
    q = base64.b64encode(json.dumps({"issuingCompany": cod, "language": "pt-br"}).encode()).decode()
    u = f"https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{q}"
    try:
        r = requests.get(u, headers=H, timeout=30); print(cod, r.status_code, len(r.content))
        d = r.json()
        d = d[0] if isinstance(d, list) else d
        print(" chaves:", list(d.keys()))
        for p in (d.get("cashDividends") or [])[:10]:
            print("  ", {k: p.get(k) for k in ("assetIssued", "paymentDate", "rate", "relatedTo", "approvedOn", "isinCode", "label", "lastDatePrior", "remarks")})
        for p in (d.get("stockDividends") or [])[:3]:
            print("  ação:", p)
    except Exception as e:
        print(cod, "erro", type(e).__name__, str(e)[:200])
