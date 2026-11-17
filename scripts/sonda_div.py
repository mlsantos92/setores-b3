import yfinance as yf
for t in ("WEGE3.SA","MDNE3.SA","POMO4.SA","PETR4.SA"):
    tk=yf.Ticker(t); d=tk.dividends; d=d[d.index>="2025-06-01"]
    print(t, "soma desde 17/11/2025:", round(float(d[d.index>="2025-11-17"].sum()),4))
    print(d.to_string())
    h=yf.download(t,period="18mo",interval="1d",auto_adjust=False,actions=True,progress=False)
    dv=h["Dividends"].squeeze(); print("download actions:", dv[dv>0].tail(12).to_string())
