"""Converte a lista original (texto) em data/raw/universo.csv.

Uso:  python scripts/montar_universo.py
"""
import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "data" / "raw" / "lista_original.txt"
DESTINO = RAIZ / "data" / "raw" / "universo.csv"

LISTAS = {"Lista 1": "Large e Mid Caps", "Lista 2": "Small e Micro Caps"}


def ler(texto: str) -> list[dict]:
    linhas, lista, setor, subsetor = [], None, None, ""
    for bruta in texto.splitlines():
        l = bruta.strip()
        if not l:
            continue
        if l.startswith("Lista "):
            lista = LISTAS[l.split(":")[0]]
            # a linha da Lista 2 traz o primeiro setor colado ("...1. Financeiro:")
            l = l.split(")", 1)[1].strip() if ")" in l else ""
            if not l:
                continue
        m = re.match(r"^(\d+)\.\s*(.+?):$", l)
        if m:
            partes = [p.strip() for p in m.group(2).split("—")]
            setor, subsetor = partes[0], (partes[1] if len(partes) > 1 else "")
            continue
        m = re.match(r"^(.+?)\s*\(([A-Z0-9, ]+)\)$", l)
        if not m:
            raise ValueError(f"linha não reconhecida: {l!r}")
        tickers = [t.strip() for t in m.group(2).split(",")]
        linhas.append({"lista": lista, "setor": setor, "subsetor": subsetor,
                       "empresa": m.group(1).strip(), "tickers": " ".join(tickers)})
    return linhas


if __name__ == "__main__":
    linhas = ler(ORIGEM.read_text(encoding="utf-8"))
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lista", "setor", "subsetor", "empresa", "tickers"])
        w.writeheader()
        w.writerows(linhas)
    print(len(linhas), "empresas,", sum(len(l["tickers"].split()) for l in linhas), "códigos")
