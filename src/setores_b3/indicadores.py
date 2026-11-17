"""Indicadores fundamentalistas de uma empresa, no padrão dos sites de análise de ações.

Entradas: o histórico trimestral da CVM (``cvm.trimestres_empresa``), o valor de mercado atual,
o preço do código e o dividend yield. Resultados de fluxo (receita, lucro, EBITDA...) são os dos
últimos 12 meses (soma dos 4 trimestres terminados no trimestre mais recente). Contas do balanço
são as do fim desse trimestre.

Convenções:
- Dívida líquida = empréstimos e financiamentos − (caixa e equivalentes + aplicações financeiras
  de curto prazo). EV = valor de mercado + dívida líquida (minoritários não entram).
- Ações equivalentes ao código = valor de mercado ÷ preço do código. Assim VPA e LPA ficam na mesma
  base do preço (inclusive em units) e P/VP = preço ÷ VPA.
- Divisão por denominador nulo ou negativo dá None (P/L de empresa com prejuízo, por exemplo).
  Exceções, como nos sites de referência: P/Capital de giro, P/Ativo circulante líquido e PEG
  aceitam denominador negativo, porque o sinal tem leitura própria.
- ROIC = EBIT × (1 − 34%) ÷ (patrimônio + dívida líquida, se positiva). A alíquota é a nominal de IR e CSLL.
- P/Ativo circulante líquido = valor de mercado ÷ (ativo circulante − passivo total, incluindo o patrimônio).
- CAGR de 5 anos: receita e lucro do último ano civil completo contra os de 5 anos antes.
"""
from __future__ import annotations

ALIQUOTA = 0.34
FLUXOS = ("receita", "bruto", "ebit", "ebitda", "lucro")
BALANCO = ("pl", "passivo", "divida", "ativo", "ativo_circ", "passivo_circ", "caixa")

GRUPOS = {
    "valuation": ["dy", "pl", "peg", "pvp", "ev_ebitda", "ev_ebit", "p_ebitda", "p_ebit", "vpa", "p_ativo", "lpa", "psr",
                  "p_capgiro", "p_acl"],
    "endividamento": ["dl_pl", "dl_ebitda", "dl_ebit", "pl_ativos", "passivos_ativos", "liq_corrente"],
    "eficiencia": ["m_bruta", "m_ebitda", "m_ebit", "m_liquida"],
    "rentabilidade": ["roe", "roa", "roic", "giro_ativos"],
    "crescimento": ["cagr_receita", "cagr_lucro"],
}
TODOS = [k for g in GRUPOS.values() for k in g]


def _idx(rotulo: str) -> int:
    """'2026T3' -> número sequencial do trimestre."""
    return int(rotulo[:4]) * 4 + int(rotulo[5:]) - 1


def _rot(i: int) -> str:
    return f"{i // 4}T{i % 4 + 1}"


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def razao(n, d, negativo: bool = False):
    """n ÷ d. Com d nulo, ausente ou (salvo ``negativo``) menor ou igual a zero, devolve None."""
    n, d = _num(n), _num(d)
    if n is None or d is None or d == 0 or (d < 0 and not negativo):
        return None
    return n / d


def doze_meses(hist: dict[str, dict], fim: str, chave: str):
    """Soma de ``chave`` nos 4 trimestres terminados em ``fim``. Falta um trimestre: None."""
    i = _idx(fim)
    vals = [_num(hist.get(_rot(j), {}).get(chave)) for j in range(i - 3, i + 1)]
    return None if any(v is None for v in vals) else sum(vals)


def ultimo_trimestre(hist: dict[str, dict]) -> str | None:
    """Trimestre mais recente com lucro dos 12 meses e patrimônio informados."""
    for rot in sorted(hist, key=_idx, reverse=True):
        if _num(hist[rot].get("pl")) is not None and doze_meses(hist, rot, "lucro") is not None:
            return rot
    return None


def cagr(atual, antes, anos: int = 5):
    a, b = _num(atual), _num(antes)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return (a / b) ** (1 / anos) - 1


def calcular(hist: dict[str, dict], valor_mercado, preco, dy=None) -> dict:
    """Todos os indicadores de GRUPOS para uma empresa. Devolve {} se faltar base."""
    fim = ultimo_trimestre(hist)
    vm, preco = _num(valor_mercado), _num(preco)
    if fim is None:
        return {}
    f = {k: doze_meses(hist, fim, k) for k in FLUXOS}
    b = {k: _num(hist[fim].get(k)) for k in BALANCO}
    divida, caixa = b["divida"], b["caixa"]
    dl = None if divida is None else divida - (caixa or 0.0)
    ev = None if vm is None or dl is None else vm + dl
    acoes = razao(vm, preco)
    capgiro = None if b["ativo_circ"] is None or b["passivo_circ"] is None else b["ativo_circ"] - b["passivo_circ"]
    # como nos sites de referência: ativo circulante − passivo total (que inclui o patrimônio)
    acl = None if b["ativo_circ"] is None or b["ativo"] is None else b["ativo_circ"] - b["ativo"]
    # capital investido: patrimônio + dívida líquida; caixa líquido não reduz o capital
    capital = None if b["pl"] is None else b["pl"] + max(dl or 0.0, 0.0)
    nopat = None if f["ebit"] is None else f["ebit"] * (1 - ALIQUOTA)
    # CAGR: último ano civil completo contra o de 5 anos antes
    ano = int(fim[:4]) if fim.endswith("T4") else int(fim[:4]) - 1
    cg_rec = cagr(doze_meses(hist, f"{ano}T4", "receita"), doze_meses(hist, f"{ano - 5}T4", "receita"))
    cg_luc = cagr(doze_meses(hist, f"{ano}T4", "lucro"), doze_meses(hist, f"{ano - 5}T4", "lucro"))
    p_l = razao(vm, f["lucro"])
    out = {
        "ind_ate": fim,
        "dy": _num(dy),
        "pl": p_l,
        "peg": None if p_l is None or not cg_luc else p_l / (cg_luc * 100),
        "pvp": razao(vm, b["pl"]),
        "ev_ebitda": razao(ev, f["ebitda"]),
        "ev_ebit": razao(ev, f["ebit"]),
        "p_ebitda": razao(vm, f["ebitda"]),
        "p_ebit": razao(vm, f["ebit"]),
        "vpa": razao(b["pl"], acoes),
        "p_ativo": razao(vm, b["ativo"]),
        "lpa": razao(f["lucro"], acoes),
        "psr": razao(vm, f["receita"]),
        "p_capgiro": razao(vm, capgiro, negativo=True),
        "p_acl": razao(vm, acl, negativo=True),
        "dl_pl": razao(dl, b["pl"]),
        "dl_ebitda": razao(dl, f["ebitda"]),
        "dl_ebit": razao(dl, f["ebit"]),
        "pl_ativos": razao(b["pl"], b["ativo"]),
        "passivos_ativos": razao(b["passivo"], b["ativo"]),
        "liq_corrente": razao(b["ativo_circ"], b["passivo_circ"]),
        "m_bruta": razao(f["bruto"], f["receita"]),
        "m_ebitda": razao(f["ebitda"], f["receita"]),
        "m_ebit": razao(f["ebit"], f["receita"]),
        "m_liquida": razao(f["lucro"], f["receita"]),
        "roe": razao(f["lucro"], b["pl"]),
        "roa": razao(f["lucro"], b["ativo"]),
        "roic": razao(nopat, capital),
        "giro_ativos": razao(f["receita"], b["ativo"]),
        "cagr_receita": cg_rec,
        "cagr_lucro": cg_luc,
        "lucro_12m_hist": f["lucro"],
        "prejuizo_12m": f["lucro"] is not None and f["lucro"] < 0,
    }
    return out
