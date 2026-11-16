"""Selo de situação do painel.

Verde:    preços do último pregão fechado para as large e mid caps, fundamentos disponíveis e testes passando.
Amarelo:  preços atrasados ou fundamentos faltando em parte relevante.
Vermelho: coleta falhou ou testes falharam.

Small e micro caps ficam fora do selo: muitas não negociam todos os dias.
"""
from __future__ import annotations

from datetime import date, datetime

from .calendario import BRT

COBERTURA_PRECO = 0.95
COBERTURA_FUNDAMENTOS = 0.80


def avaliar(empresas: list[dict], esperado: date, testes_ok: bool, agora: datetime | None = None) -> dict:
    agora = (agora or datetime.now(BRT)).astimezone(BRT)
    grandes = [e for e in empresas if e["lista"] == "Large e Mid Caps" and e.get("ticker")]
    eleg = [e for e in empresas if e.get("elegivel")]
    em_dia = sum(1 for e in grandes if e.get("ultimo_preco_em") == esperado.isoformat())
    com_fund = sum(1 for e in eleg if e.get("pvp") is not None or e.get("pl") is not None)
    cob_preco = em_dia / len(grandes) if grandes else 0.0
    cob_fund = com_fund / len(eleg) if eleg else 0.0

    if not testes_ok or not grandes or len(eleg) < 20:
        cor, motivo = "vermelho", "coleta ou testes falharam"
    elif cob_preco < COBERTURA_PRECO:
        cor, motivo = "amarelo", f"só {em_dia} de {len(grandes)} large e mid caps com preço de {esperado:%d/%m}"
    elif cob_fund < COBERTURA_FUNDAMENTOS:
        cor, motivo = "amarelo", f"fundamentos em {com_fund} de {len(eleg)} empresas elegíveis"
    else:
        cor, motivo = "verde", "preços do último pregão, fundamentos disponíveis e testes passando"
    return {"cor": cor, "motivo": motivo, "pregao_esperado": esperado.isoformat(),
            "cobertura_preco": round(cob_preco, 4), "cobertura_fundamentos": round(cob_fund, 4),
            "testes": "ok" if testes_ok else "falha", "atualizado_em": agora.strftime("%Y-%m-%d %H:%M")}
