"""Universo do estudo: empresas, setores e códigos (data/raw/universo.csv) e ajustes de código."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"


def carregar(caminho: Path | None = None) -> pd.DataFrame:
    """Uma linha por empresa; ``tickers`` vira lista."""
    u = pd.read_csv(caminho or RAW / "universo.csv", keep_default_na=False)
    u["tickers"] = u["tickers"].str.split()
    return u


def carregar_ajustes(caminho: Path | None = None) -> dict:
    """Códigos que mudaram (renomear) e empresas que saíram da bolsa (fora)."""
    d = json.loads((caminho or RAW / "ajustes_tickers.json").read_text(encoding="utf-8"))
    return {"renomear": d.get("renomear", {}), "fora": d.get("fora", {}), "cnpj": d.get("cnpj", {})}


def aplicar_ajustes(u: pd.DataFrame, ajustes: dict) -> pd.DataFrame:
    """Troca códigos antigos pelos atuais (sem repetir) e guarda os originais em ``tickers_lista``."""
    ren = ajustes["renomear"]
    out = u.copy()
    out["tickers_lista"] = out["tickers"]
    out["tickers"] = [list(dict.fromkeys(ren.get(t, t) for t in ts)) for ts in out["tickers"]]
    return out
