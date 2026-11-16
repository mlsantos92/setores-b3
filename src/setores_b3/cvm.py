"""Resultados oficiais das empresas: demonstrações protocoladas na CVM (DFP anual, auditada,
e ITR trimestral, revisada pelo auditor independente), mais o nome do auditor de cada empresa.

O estudo usa só as métricas das demonstrações. O parecer do auditor não é lido nem avaliado.

Fonte: Portal de Dados Abertos da CVM (dados.cvm.gov.br), conjuntos DFP, ITR e FCA.
Só ``baixar`` fala com a rede; as demais funções recebem tabelas.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile

import pandas as pd
import requests

BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


# ------------------------------------------------------------------ rede
def _zip(caminho: str, timeout: int = 240) -> zipfile.ZipFile | None:
    r = requests.get(BASE + caminho, timeout=timeout)
    if r.status_code != 200:
        print(f"CVM: {caminho} respondeu {r.status_code}")
        return None
    return zipfile.ZipFile(io.BytesIO(r.content))


def _csv(z: zipfile.ZipFile | None, nome: str, cnpjs: set[str] | None = None) -> pd.DataFrame:
    """Lê um CSV do zip. Com ``cnpjs``, guarda só essas empresas e as contas até o 3º nível."""
    if z is None or nome not in z.namelist():
        return pd.DataFrame()
    d = pd.read_csv(z.open(nome), sep=";", encoding="latin1", dtype=str)
    if cnpjs is not None and "CNPJ_CIA" in d:
        d = d[d["CNPJ_CIA"].isin(cnpjs)]
        if "CD_CONTA" in d:
            d = d[d["CD_CONTA"].str.len() <= 7]
    return d


def baixar_cadastro(ano: int) -> dict[str, pd.DataFrame]:
    """FCA do ano e do anterior: códigos de negociação, site e auditor."""
    tab = {}
    zips = [(a, _zip(f"FCA/DADOS/fca_cia_aberta_{a}.zip")) for a in (ano - 1, ano)]
    for nome in ("valor_mobiliario", "geral", "auditor"):
        partes = [_csv(z, f"fca_cia_aberta_{nome}_{a}.csv") for a, z in zips]
        partes = [p for p in partes if len(p)]
        tab[f"fca_{nome}"] = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return tab


def baixar_demonstracoes(ano: int, anos_atras: int = 1, cnpjs: set[str] | None = None) -> dict[str, pd.DataFrame]:
    """DFP e ITR de ``ano - anos_atras`` até ``ano``: DRE, balanço (passivo) e composição do capital."""
    out: dict[str, list] = {k: [] for k in ("dre_con", "dre_ind", "bpp_con", "bpp_ind", "capital")}
    for a in range(ano - anos_atras, ano + 1):
        for tipo in ("DFP", "ITR"):
            z = _zip(f"{tipo}/DADOS/{tipo.lower()}_cia_aberta_{a}.zip")
            for parte in ("DRE_con", "DRE_ind", "BPP_con", "BPP_ind", "DVA_con", "DVA_ind"):
                d = _csv(z, f"{tipo.lower()}_cia_aberta_{parte}_{a}.csv", cnpjs)
                if len(d):
                    # a DVA entra na mesma tabela da DRE: dela só interessa a depreciação e amortização
                    out[parte.lower().replace("dva", "dre")].append(d.assign(TIPO=tipo))
            d = _csv(z, f"{tipo.lower()}_cia_aberta_composicao_capital_{a}.csv", cnpjs)
            if len(d):
                out["capital"].append(d)
    return {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in out.items()}


# ------------------------------------------------------------------ cadastro
def mapa_tickers(fca_vm: pd.DataFrame) -> dict[str, str]:
    """Código de negociação -> CNPJ da companhia (o cadastro mais recente vence)."""
    if not len(fca_vm):
        return {}
    d = fca_vm.dropna(subset=["Codigo_Negociacao"]).sort_values(["Data_Referencia", "Versao"])
    return {str(t).strip().upper(): c for t, c in zip(d["Codigo_Negociacao"], d["CNPJ_Companhia"])}


def sites(fca_geral: pd.DataFrame) -> dict[str, str]:
    if not len(fca_geral) or "Pagina_Web" not in fca_geral:
        return {}
    d = fca_geral.dropna(subset=["Pagina_Web"]).sort_values(["Data_Referencia", "Versao"])
    out = {}
    for c, s in zip(d["CNPJ_Companhia"], d["Pagina_Web"]):
        s = str(s).strip()
        if "." in s and " " not in s:
            out[c] = s if s.lower().startswith("http") else "https://" + s
    return out


def auditores(fca_auditor: pd.DataFrame) -> dict[str, dict]:
    """CNPJ -> auditor independente atual (o de início de atuação mais recente, sem data de fim)."""
    if not len(fca_auditor) or "Auditor" not in fca_auditor:
        return {}
    d = fca_auditor.dropna(subset=["Auditor"]).copy()
    ini = next((c for c in d.columns if "Inicio" in c and "Atua" in c), None)
    fim = next((c for c in d.columns if "Fim" in c and "Atua" in c), None)
    if fim:
        abertos = d[d[fim].isna()]
        d = pd.concat([d[~d["CNPJ_Companhia"].isin(abertos["CNPJ_Companhia"])], abertos])
    d = d.sort_values(["Data_Referencia", "Versao"] + ([ini] if ini else []))
    out = {}
    for c, a in zip(d["CNPJ_Companhia"], d["Auditor"]):
        nome = re.sub(r"\s+", " ", str(a)).strip()
        out[c] = {"auditor": nome}
    return out


def capital(tab_capital: pd.DataFrame) -> dict[str, dict]:
    """CNPJ -> ações em circulação fora da tesouraria, por espécie (ON e PN), no documento mais recente."""
    if not len(tab_capital):
        return {}
    col = {k: next((c for c in tab_capital.columns if p in c.upper()), None)
           for k, p in (("on", "ORDIN_CAP"), ("pn", "PREF_CAP"), ("on_tes", "ORDIN_TESOURO"), ("pn_tes", "PREF_TESOURO"))}
    if not col["on"] or not col["pn"]:
        return {}
    d = tab_capital.sort_values(["DT_REFER", "VERSAO"])
    out = {}
    for linha in d.to_dict("records"):
        n = lambda k: float(pd.to_numeric(linha.get(col[k]), errors="coerce") or 0) if col[k] else 0.0  # noqa: E731
        on, pn = n("on") - n("on_tes"), n("pn") - n("pn_tes")
        if on + pn > 0:
            out[linha["CNPJ_CIA"]] = {"acoes_on": on, "acoes_pn": pn}
    return out


def composicao_units(fca_vm: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Código da unit -> (ações ON, ações PN) que ela representa, lido de textos como '1 ON / 2 PN'."""
    if not len(fca_vm) or "Composicao_BDR_Unit" not in fca_vm:
        return {}
    out = {}
    d = fca_vm.dropna(subset=["Codigo_Negociacao", "Composicao_BDR_Unit"]).sort_values(["Data_Referencia", "Versao"])
    for t, texto in zip(d["Codigo_Negociacao"], d["Composicao_BDR_Unit"]):
        alto = _norm(texto).upper()
        on = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ACAO|ACOES)?\s*(?:ON|ORDINARIA)", alto)
        pn = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ACAO|ACOES)?\s*(?:PN|PREFERENCIA)", alto)
        if on or pn:
            num = lambda m: float(m.group(1).replace(",", ".")) if m else 0.0  # noqa: E731
            out[str(t).strip().upper()] = (num(on), num(pn))
    return out


# ------------------------------------------------------------------ demonstrações
def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    if not len(df):
        return df
    d = df.copy()
    d["VERSAO"] = d["VERSAO"].astype(int)
    ult = d.groupby(["CNPJ_CIA", "DT_REFER", "TIPO"])["VERSAO"].transform("max")
    d = d[d["VERSAO"] == ult].copy()
    escala = d["ESCALA_MOEDA"].map(lambda e: 1000.0 if _norm(e).startswith("mil") else 1.0)
    d["VALOR"] = pd.to_numeric(d["VL_CONTA"], errors="coerce") * escala
    d["DS"] = d["DS_CONTA"].map(_norm)
    d["ULTIMO"] = d["ORDEM_EXERC"].map(lambda o: not _norm(o).startswith("pen"))
    return d


def _acumulado(doc: pd.DataFrame, ultimo: bool) -> pd.DataFrame:
    """Linhas do período acumulado (o que começa mais cedo) do exercício pedido."""
    x = doc[doc["ULTIMO"] == ultimo]
    return x[x["DT_INI_EXERC"] == x["DT_INI_EXERC"].min()] if len(x) else x


def _conta(x: pd.DataFrame, *prefixos: str, nivel: int | None = 4, pai: str | None = None) -> float | None:
    y = x
    if nivel:
        y = y[y["CD_CONTA"].str.len() == nivel]
    if pai:
        y = y[y["CD_CONTA"].str.startswith(pai + ".")]
    # astype(bool): com zero linhas o map devolve uma série sem tipo, que o pandas leria como lista de colunas
    y = y[y["DS"].map(lambda s: any(s.startswith(p) for p in prefixos)).astype(bool)]
    v = y["VALOR"].dropna()
    return float(v.iloc[0]) if len(v) else None


def _dre(x: pd.DataFrame) -> dict:
    """Receita, resultado operacional e lucro de um período da DRE."""
    if not len(x):
        return {}
    linha = x[(x["CD_CONTA"].str.len() == 4)
              & x["DS"].map(lambda s: s.startswith(("lucro/prejuizo consolidado do periodo", "lucro/prejuizo do periodo",
                                                    "lucro ou prejuizo liquido consolidado do periodo",
                                                    "lucro ou prejuizo liquido do periodo"))).astype(bool)]
    if not len(linha):
        return {}
    cd = linha["CD_CONTA"].iloc[0]
    lucro = float(linha["VALOR"].iloc[0])
    ctrl = _conta(x, "atribuido a socios da empresa controladora", nivel=7, pai=cd)
    receita = x[x["CD_CONTA"] == "3.01"]["VALOR"]
    return {"lucro": ctrl if ctrl not in (None, 0.0) or lucro == 0 else lucro,
            "receita": float(receita.iloc[0]) if len(receita) and pd.notna(receita.iloc[0]) else None,
            "ebit": _conta(x, "resultado antes do resultado financeiro e dos tributos"),
            "da": _conta(x, "depreciacao, amortizacao", nivel=7),
            "ini": x["DT_INI_EXERC"].iloc[0], "fim": x["DT_FIM_EXERC"].iloc[0]}


def _patrimonio(bpp_doc: pd.DataFrame) -> float | None:
    x = bpp_doc[bpp_doc["ULTIMO"]]
    linha = x[(x["CD_CONTA"].str.len() == 4) & x["DS"].map(lambda s: s.startswith("patrimonio liquido")).astype(bool)]
    if not len(linha):
        return None
    total = float(linha["VALOR"].iloc[0])
    minor = _conta(x, "participacao dos acionistas nao controladores", nivel=7, pai=linha["CD_CONTA"].iloc[0])
    return total - (minor or 0.0)


def _balanco(bpp_doc: pd.DataFrame) -> dict:
    """Do balanço de uma data: patrimônio dos controladores, passivo exigível e dívida bruta.

    Passivo exigível = passivo total − patrimônio líquido total (tudo o que a empresa deve).
    Dívida bruta = empréstimos e financiamentos de curto e longo prazo (bancos não têm essa linha).
    """
    pl = _patrimonio(bpp_doc)
    if pl is None:
        return {}
    x = bpp_doc[bpp_doc["ULTIMO"]]
    total = _conta(x, "passivo total", nivel=1)
    pl_total = _conta(x, "patrimonio liquido")
    divida = x[(x["CD_CONTA"].str.len() == 7) & x["DS"].map(lambda t: t.startswith("emprestimos e financiamentos")).astype(bool)]["VALOR"].dropna()
    return {"pl": pl,
            "passivo": None if total is None or pl_total is None else total - pl_total,
            "divida": float(divida.sum()) if len(divida) else None}


def resultado_empresa(dre: pd.DataFrame, bpp: pd.DataFrame) -> dict:
    """Lucro e receita dos últimos 12 meses e patrimônio líquido mais recente de UMA empresa.

    Últimos 12 meses = último exercício anual (DFP) + acumulado do ano corrente (ITR)
    − acumulado do mesmo período do ano anterior (vem no próprio ITR).
    ``dre`` e ``bpp`` já preparados e filtrados para a empresa.
    """
    if not len(dre):
        return {}
    ref = dre["DT_REFER"].max()
    doc = dre[dre["DT_REFER"] == ref]
    tipo = "DFP" if (doc["TIPO"] == "DFP").any() else "ITR"
    doc = doc[doc["TIPO"] == tipo]
    atual = _dre(_acumulado(doc, True))
    if not atual:
        return {}
    out = {"resultado_ate": ref, "documento": tipo}
    if tipo == "DFP":
        ltm = atual
    else:
        anterior = _dre(_acumulado(doc, False))
        fim_anual = (pd.Timestamp(atual["ini"]) - pd.Timedelta(days=1)).date().isoformat()
        anual_doc = dre[(dre["TIPO"] == "DFP") & (dre["DT_REFER"] == fim_anual)]
        anual = _dre(_acumulado(anual_doc, True)) if len(anual_doc) else {}
        if not anterior or not anual:
            ltm = {}
        else:
            ltm = {k: (None if None in (anual.get(k), atual.get(k), anterior.get(k))
                       else anual[k] + atual[k] - anterior[k]) for k in ("lucro", "receita", "ebit")}
    out.update({"lucro_12m": ltm.get("lucro"), "receita_12m": ltm.get("receita"), "ebit_12m": ltm.get("ebit")})
    b = bpp[(bpp["DT_REFER"] == ref) & (bpp["TIPO"] == tipo)] if len(bpp) else bpp
    out["patrimonio"] = _patrimonio(b) if len(b) else None
    return out


def resultados(tab: dict[str, pd.DataFrame], cnpjs: set[str]) -> dict[str, dict]:
    """CNPJ -> resultado. Vale a visão (consolidada ou individual) com o documento mais recente;
    no empate, a consolidada. Há empresas que deixaram de consolidar e seguem só com a individual."""
    prep = {}
    for k in ("dre_con", "dre_ind", "bpp_con", "bpp_ind"):
        d = tab.get(k, pd.DataFrame())
        prep[k] = _preparar(d[d["CNPJ_CIA"].isin(cnpjs)]) if len(d) else d
    out = {}
    for c in cnpjs:
        for visao in ("con", "ind"):
            dre, bpp = prep[f"dre_{visao}"], prep[f"bpp_{visao}"]
            if not len(dre):
                continue
            r = resultado_empresa(dre[dre["CNPJ_CIA"] == c], bpp[bpp["CNPJ_CIA"] == c] if len(bpp) else bpp)
            if r and (r.get("lucro_12m") is not None or r.get("patrimonio") is not None):
                if c not in out or r["resultado_ate"] > out[c]["resultado_ate"]:
                    out[c] = {**r, "visao": "consolidado" if visao == "con" else "individual"}
    return out


def cnpjs_dos_tickers(fca_vm: pd.DataFrame, tickers: list[str], irmaos: dict[str, list[str]] | None = None,
                      cnpj_manual: dict[str, str] | None = None) -> dict[str, str]:
    """Código -> CNPJ, tentando o próprio código, depois os irmãos; o CNPJ manual vence o cadastro."""
    mapa = {**mapa_tickers(fca_vm), **(cnpj_manual or {})}   # o cadastro da CVM não traz o código de todas
    cnpj = {}
    for t in tickers:
        achado = next((mapa[x] for x in [t] + list((irmaos or {}).get(t, [])) if x in mapa), None)
        if achado:
            cnpj[t] = achado
    return cnpj


# ------------------------------------------------------------------ histórico por trimestre
def rotulo_trimestre(fim: str) -> str:
    """Trimestre civil em que o período termina: '2026-09-30' -> '2026T3'."""
    d = pd.Timestamp(fim)
    return f"{d.year}T{(d.month - 1) // 3 + 1}"


ORIGINAL, TRIMESTRE_SEGUINTE, ANO_SEGUINTE = 0, 1, 2
FLUXOS = ("receita", "ebit", "lucro", "da")


def _pontos(dre: pd.DataFrame) -> tuple[dict, dict]:
    """Lê todos os períodos de todos os documentos da empresa.

    Devolve (acumulados, isolados):
    - acumulados[(início do exercício, fim)] = resultado acumulado até a data;
    - isolados[fim] = resultado de um trimestre sozinho.
    Cada valor guarda a origem. Além do documento do próprio período (ORIGINAL), entram:
    - TRIMESTRE_SEGUINTE: o ITR seguinte traz o acumulado e o trimestre isolado; a diferença
      é o acumulado até o trimestre anterior;
    - ANO_SEGUINTE: os documentos do ano seguinte repetem, na coluna do exercício anterior,
      o acumulado e o trimestre do mesmo período.
    Quando há mais de uma origem para o mesmo período, vale a de menor número.
    """
    acum: dict[tuple, dict] = {}
    isol: dict[str, dict] = {}

    def guarda(destino, chave, r, origem):
        if chave not in destino or origem < destino[chave]["origem"]:
            destino[chave] = {**r, "origem": origem}

    for ref, doc in dre.groupby("DT_REFER"):
        tipo = "DFP" if (doc["TIPO"] == "DFP").any() else "ITR"      # na mesma data, a DFP (auditada) vence
        doc = doc[doc["TIPO"] == tipo]
        periodos = {}
        for (ultimo, ini, fim), linhas in doc.groupby(["ULTIMO", "DT_INI_EXERC", "DT_FIM_EXERC"]):
            r = _dre(linhas)
            if r:
                periodos[(bool(ultimo), ini, fim)] = r
        for ultimo in (True, False):
            deste = {(ini, fim): r for (u, ini, fim), r in periodos.items() if u == ultimo}
            if not deste:
                continue
            ini_ex = min(ini for ini, _ in deste)
            origem = ORIGINAL if ultimo else ANO_SEGUINTE
            cheio = next((r for (ini, _), r in deste.items() if ini == ini_ex), None)
            if cheio:
                guarda(acum, (ini_ex, cheio["fim"]), cheio, origem)
            for (ini, fim), r in deste.items():
                dias = (pd.Timestamp(fim) - pd.Timestamp(ini)).days
                if ini != ini_ex and 80 <= dias <= 100:
                    guarda(isol, fim, r, origem)
                    if cheio and cheio["fim"] == fim:        # acumulado − trimestre = acumulado do trimestre anterior
                        antes = (pd.Timestamp(ini) - pd.Timedelta(days=1)).date().isoformat()
                        dif = {k: (None if cheio.get(k) is None or r.get(k) is None else cheio[k] - r[k])
                               for k in FLUXOS}
                        guarda(acum, (ini_ex, antes), {**dif, "ini": ini_ex, "fim": antes},
                               max(origem, TRIMESTRE_SEGUINTE))
    return acum, isol


def trimestres_empresa(dre: pd.DataFrame, bpp: pd.DataFrame) -> dict[str, dict]:
    """Resultado de cada trimestre isolado de UMA empresa, por rótulo ('2026T3').

    Cada documento traz o acumulado do exercício até a data-base. O trimestre é a diferença entre
    dois acumulados seguidos do mesmo exercício (o 4º trimestre sai da DFP menos o ITR do 3º).
    Se falta o documento de um período, o valor é buscado no trimestre seguinte ou no mesmo
    período do ano seguinte (ver ``_pontos``) e o trimestre sai marcado com ``cruzado``.
    Sem nenhuma dessas referências, o trimestre fica vazio: nada é estimado.
    ``dre`` e ``bpp`` já preparados e filtrados para a empresa.
    """
    if not len(dre):
        return {}
    acum, isol = _pontos(dre)
    exercicios: dict[str, list] = {}
    for (ini, _), r in acum.items():
        exercicios.setdefault(ini, []).append(r)
    out = {}
    for ini, lista in exercicios.items():
        lista.sort(key=lambda r: r["fim"])
        ant = None
        for r in lista:
            inicio = pd.Timestamp(ant["fim"]) if ant else pd.Timestamp(ini) - pd.Timedelta(days=1)
            dias = (pd.Timestamp(r["fim"]) - inicio).days
            if 80 <= dias <= 100:
                q = {k: (None if r.get(k) is None or (ant and ant.get(k) is None) else r[k] - (ant[k] if ant else 0.0))
                     for k in FLUXOS}
                origem = max(r["origem"], ant["origem"] if ant else ORIGINAL)
                rot = rotulo_trimestre(r["fim"])
                if rot not in out or origem < out[rot]["origem"]:
                    out[rot] = {**q, "fim": r["fim"], "origem": origem}
            ant = r
    for fim, r in isol.items():                      # trimestre isolado informado direto, se a diferença não deu
        rot = rotulo_trimestre(fim)
        if rot not in out or r["origem"] < out[rot]["origem"]:
            out[rot] = {k: r.get(k) for k in FLUXOS} | {"fim": fim, "origem": r["origem"]}
    for q in out.values():      # EBITDA = resultado operacional + depreciação e amortização (vem da DVA, negativa)
        da = q.pop("da", None)
        q["ebitda"] = None if q.get("ebit") is None or da is None else q["ebit"] + abs(da)
    if len(bpp):
        # balanço: o do próprio documento; se faltar, o que um documento posterior repete como exercício anterior
        bal: dict[str, tuple] = {}
        for (ref, ultimo, fim), b in bpp.groupby(["DT_REFER", "ULTIMO", "DT_FIM_EXERC"]):
            tipo = "DFP" if (b["TIPO"] == "DFP").any() else "ITR"
            v = _balanco(b[b["TIPO"] == tipo].assign(ULTIMO=True))
            origem = ORIGINAL if ultimo else ANO_SEGUINTE
            if v.get("pl") is not None and (fim not in bal or origem < bal[fim][1]):
                bal[fim] = (v, origem)
        for q in out.values():
            if q["fim"] in bal:
                q.update(bal[q["fim"]][0])
                if q.get("lucro") is None:
                    q["origem"] = max(q["origem"], bal[q["fim"]][1])
    for q in out.values():
        q["cruzado"] = q.pop("origem") != ORIGINAL
    return out


def mesclar(antigo: dict[str, dict], novo: dict[str, dict]) -> dict[str, dict]:
    """Junta trimestres já guardados com os recém-calculados. O novo entra por cima, menos quando
    é um valor cruzado e o guardado veio do documento original do período."""
    out = dict(antigo)
    for rot, q in novo.items():
        if rot in out and q.get("cruzado") and not out[rot].get("cruzado"):
            continue
        out[rot] = q
    return out


def historico(tab: dict[str, pd.DataFrame], cnpj_por_ticker: dict[str, str]) -> dict[str, dict]:
    """Código -> {rótulo do trimestre -> receita, EBIT, lucro e patrimônio}. Consolidado; senão, individual."""
    cnpjs = set(cnpj_por_ticker.values())
    prep = {}
    for k in ("dre_con", "dre_ind", "bpp_con", "bpp_ind"):
        d = tab.get(k, pd.DataFrame())
        prep[k] = _preparar(d[d["CNPJ_CIA"].isin(cnpjs)]) if len(d) else d
    por_cnpj = {}
    for c in cnpjs:
        junto: dict[str, dict] = {}
        for visao in ("ind", "con"):               # o consolidado entra por último e vence
            dre, bpp = prep[f"dre_{visao}"], prep[f"bpp_{visao}"]
            if len(dre):
                junto.update(trimestres_empresa(dre[dre["CNPJ_CIA"] == c], bpp[bpp["CNPJ_CIA"] == c] if len(bpp) else bpp))
        if junto:
            por_cnpj[c] = junto
    return {t: por_cnpj[c] for t, c in cnpj_por_ticker.items() if c in por_cnpj}


def oficiais(tab: dict[str, pd.DataFrame], tickers: list[str], irmaos: dict[str, list[str]] | None = None,
             cnpj_manual: dict[str, str] | None = None) -> dict[str, dict]:
    """Código -> resultado oficial + auditor + capital + site, para os códigos que a CVM conhece.

    ``irmaos`` lista, por código, outros códigos da mesma empresa (outra classe de ação ou o
    código antigo): servem para achar o cadastro quando o código escolhido não aparece nele.
    """
    vm = tab.get("fca_valor_mobiliario", pd.DataFrame())
    cnpj = cnpjs_dos_tickers(vm, tickers, irmaos, cnpj_manual)
    res = resultados(tab, set(cnpj.values()))
    aud = auditores(tab.get("fca_auditor", pd.DataFrame()))
    web = sites(tab.get("fca_geral", pd.DataFrame()))
    cap = capital(tab.get("capital", pd.DataFrame()))
    units = composicao_units(vm)
    out = {}
    for t, c in cnpj.items():
        d = {**res.get(c, {}), **aud.get(c, {}), **cap.get(c, {}), "cnpj": c}
        if c in web:
            d["site"] = web[c]
        if t in units:
            d["unit"] = units[t]
        out[t] = d
    return out
