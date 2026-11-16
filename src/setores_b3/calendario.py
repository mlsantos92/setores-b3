"""Calendário de pregões da B3: dias úteis menos feriados nacionais e os dias sem pregão."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")


def pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados(ano: int) -> set[date]:
    p = pascoa(ano)
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 24), (12, 25), (12, 31)]
    moveis = [p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2), p + timedelta(days=60)]
    return {date(ano, m, d) for m, d in fixos} | set(moveis)


def eh_pregao(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados(d.year)


def ultimo_pregao_fechado(agora: datetime | None = None) -> date:
    """Último pregão já encerrado em Brasília (o do dia conta a partir das 18h30)."""
    agora = (agora or datetime.now(BRT)).astimezone(BRT)
    fechou = (agora.hour, agora.minute) >= (18, 30)
    d = agora.date() if fechou else agora.date() - timedelta(days=1)
    while not eh_pregao(d):
        d -= timedelta(days=1)
    return d
