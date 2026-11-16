"""Sonda: confere se o Yahoo Finance responde do GitHub Actions e o que ele devolve."""
import json
import yfinance as yf

for tk in ["PETR4.SA", "ITUB4.SA", "ITUB3.SA", "RSUL4.SA", "ELET3.SA", "AXIA3.SA", "CCRO3.SA", "MOTV3.SA", "BRFS3.SA", "TAEE11.SA"]:
    try:
        t = yf.Ticker(tk)
        h = t.history(period="5y", interval="1d", auto_adjust=True)
        info = t.info or {}
        campos = {k: info.get(k) for k in ["trailingPE", "priceToBook", "enterpriseToEbitda", "dividendYield",
                                           "trailingAnnualDividendYield", "returnOnEquity", "marketCap", "profitMargins",
                                           "debtToEquity", "sector", "averageVolume", "currentPrice", "longName"]}
        print(tk, len(h), str(h.index.min())[:10], str(h.index.max())[:10], json.dumps(campos, ensure_ascii=False))
    except Exception as e:
        print(tk, "ERRO", type(e).__name__, str(e)[:200])

d = yf.download(["PETR4.SA", "VALE3.SA", "WEGE3.SA"], period="5y", interval="1d", auto_adjust=True, progress=False, group_by="ticker")
print("lote:", d.shape)
print(yf.__version__)
