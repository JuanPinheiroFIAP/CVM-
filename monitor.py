"""Monitor de Captacao - Multimercado vs Peers (dados publicos CVM).

Uso:
    python baixar_cvm.py          # baixa/atualiza os dados (cache em data/raw)
    python monitor.py             # processa e gera monitor_captacao.html

O HTML gerado e autocontido (sem internet / CDN): os peers sao calculados no
navegador, entao voce troca a definicao de peer (classe ANBIMA, publico-alvo,
faixa de PL, gestor...) sem rodar nada de novo.
"""
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
RAW = AQUI / "data" / "raw"
SAIDA = AQUI / "data" / "tmp" / "monitor_captacao.html"
TEMPLATE = AQUI / "monitor_template.html"

JANELAS = [("1d", 1), ("5d", 5), ("21d", 21), ("63d", 63), ("126d", 126), ("252d", 252), ("MTD", None), ("YTD", None)]
N_DIARIO = 63


def so_digitos(s):
    return s.str.replace(r"\D", "", regex=True)


def fmt_cnpj(c):
    c = c.zfill(14)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def ler_cadastro():
    cl = pd.read_csv(RAW / "reg" / "registro_classe.csv", sep=";", encoding="latin1", dtype=str)
    fu = pd.read_csv(RAW / "reg" / "registro_fundo.csv", sep=";", encoding="latin1", dtype=str)
    cl = cl[(cl.Classificacao == "Multimercado") & (cl.Situacao == "Em Funcionamento Normal")].copy()
    fu = fu[["ID_Registro_Fundo", "Gestor", "Administrador", "CNPJ_Fundo"]]
    cl = cl.merge(fu, on="ID_Registro_Fundo", how="left")
    cl["cnpj"] = so_digitos(cl.CNPJ_Classe)
    cl = cl.drop_duplicates("cnpj")
    return cl


def ler_informe(cnpjs):
    partes = []
    cols = ["CNPJ_FUNDO_CLASSE", "ID_SUBCLASSE", "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA", "NR_COTST"]
    for z in sorted((RAW / "inf_diario").glob("inf_diario_fi_*.zip")):
        try:
            d = pd.read_csv(z, sep=";", encoding="latin1", dtype=str, usecols=lambda c: c in cols or c == "CNPJ_FUNDO")
        except (zipfile.BadZipFile, ValueError) as e:
            print("ignorando", z.name, e)
            continue
        if "CNPJ_FUNDO" in d.columns:  # layout antigo (pre RCVM 175)
            d = d.rename(columns={"CNPJ_FUNDO": "CNPJ_FUNDO_CLASSE"})
        d["cnpj"] = so_digitos(d.CNPJ_FUNDO_CLASSE)
        d = d[d.cnpj.isin(cnpjs)]
        for c in ["VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA", "NR_COTST"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        partes.append(d[["cnpj", "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA", "NR_COTST"]])
        print("lido", z.name, len(d))
    return pd.concat(partes, ignore_index=True)


def exportar_captacao(cad, ids, PLf, COTf, JW, bases, datas, meses, MF, MP, DIA):
    """Tabelas completas (sem filtros da tela) em CSV/Excel/Parquet. Valores em R$."""
    import exportar as ex
    jn = [j[0] for j in JANELAS]
    prev = cad.Classificacao_Anbima.fillna("").str.contains("previd", case=False)
    attrs = pd.DataFrame({
        "cnpj": [fmt_cnpj(c) for c in ids], "fundo": cad.loc[ids, "Denominacao_Social"].values,
        "gestora": cad.loc[ids, "Gestor"].fillna("n/d").values, "administrador": cad.loc[ids, "Administrador"].fillna("n/d").values,
        "classe_anbima": cad.loc[ids, "Classificacao_Anbima"].fillna("Sem classificacao").values,
        "publico_alvo": cad.loc[ids, "Publico_Alvo"].fillna("n/d").values,
        "exclusivo": (cad.loc[ids, "Exclusivo"] == "S").values, "previdencia": prev.loc[ids].values,
        "fundo_de_cotas": cad.loc[ids, "Classe_Cotas"].fillna("n/d").values,
        "condominio": cad.loc[ids, "Forma_Condominio"].fillna("n/d").values,
        "data_inicio": pd.to_datetime(cad.loc[ids, "Data_Inicio"], errors="coerce").values,
        "pl_atual": PLf.iloc[:, -1].loc[ids].values, "cotistas": COTf.iloc[:, -1].loc[ids].values,
        "data_base_informe": pd.Timestamp(datas[-1])}, index=ids)
    attrs.index.name = None

    # ---- fundos: janelas (formato longo) e largo
    longos = []
    for i, w in enumerate(JW):
        d = pd.DataFrame({"janela": jn[i], "data_base": pd.Timestamp(datas[bases[i]]), "capt_liquida": w["F"], "capt_bruta": w["C"],
                          "resgate": w["R"], "pl_inicial": w["P0"], "delta_cotistas": w["DC"], "rentab_pct": w["RT"]}).loc[ids]
        d["pct_pl"] = np.where(d.pl_inicial > 0, d.capt_liquida / d.pl_inicial * 100, np.nan)
        d.insert(0, "cnpj", attrs.cnpj.values)
        longos.append(d)
    L = pd.concat(longos, ignore_index=True)
    for c in ["fundo", "gestora", "classe_anbima", "publico_alvo", "exclusivo", "previdencia"]:
        L[c] = np.tile(attrs[c].values, len(JW))
    L = L[["cnpj", "fundo", "gestora", "classe_anbima", "publico_alvo", "exclusivo", "previdencia", "janela", "data_base", "capt_liquida",
           "capt_bruta", "resgate", "pl_inicial", "pct_pl", "delta_cotistas", "rentab_pct"]]
    ex.salvar("captacao_fundos_janelas", L, "Captação líquida, bruta, resgate, PL inicial, % PL, Δ cotistas e rentabilidade de cada fundo em cada janela (1d…YTD).", "Captação · fundos")
    wide = attrs.reset_index(drop=True).copy()
    for i, j in enumerate(jn):
        d = longos[i].reset_index(drop=True)
        for col in ["capt_liquida", "capt_bruta", "resgate", "pl_inicial", "pct_pl", "delta_cotistas", "rentab_pct"]:
            wide[f"{col}_{j}"] = d[col].values
    ex.salvar("captacao_fundos", wide, "Uma linha por fundo (classe): cadastro + todas as janelas em colunas (capt_liquida_21d, pct_pl_YTD…).", "Captação · fundos")

    # ---- fundos: mensal e diário
    mens = []
    for i, m in enumerate(meses):
        mens.append(pd.DataFrame({"cnpj": attrs.cnpj.values, "mes": pd.Timestamp(m + "-01"), "capt_liquida": MF[i].loc[ids].values,
                                  "pl_inicio_mes": MP[i].loc[ids].values}))
    FM = pd.concat(mens, ignore_index=True)
    FM["pct_pl"] = np.where(FM.pl_inicio_mes > 0, FM.capt_liquida / FM.pl_inicio_mes * 100, np.nan)
    ex.salvar("captacao_fundos_mensal", FM.merge(attrs[["cnpj", "fundo", "gestora"]], on="cnpj"), "Captação líquida mensal por fundo (12 meses fechados + mês corrente).", "Captação · fundos")
    DD = DIA.loc[ids].copy()
    DD.index = attrs.cnpj.values
    FD = DD.stack().rename("capt_liquida").reset_index()
    FD.columns = ["cnpj", "data", "capt_liquida"]
    FD["data"] = pd.to_datetime(FD["data"])
    ex.salvar("captacao_fundos_diaria", FD.merge(attrs[["cnpj", "fundo", "gestora"]], on="cnpj"), f"Captação líquida diária por fundo nos últimos {N_DIARIO} pregões.", "Captação · fundos")

    # ---- gestoras
    def agrega(df, chaves):
        m = df.pl_inicial > 0
        t = df.assign(_f=df.capt_liquida.where(m, 0), _c=df.capt_bruta.where(m, 0), _r=df.resgate.where(m, 0), _p=df.pl_inicial.where(m, 0),
                      _pos=((df.capt_liquida > 0) & m).astype(int), _m=m.astype(int))
        g = t.groupby(chaves, as_index=False).agg(
            n_fundos=("cnpj", "count"), n_fundos_com_base=("_m", "sum"), capt_liquida=("_f", "sum"), capt_bruta=("_c", "sum"),
            resgate=("_r", "sum"), pl_inicial=("_p", "sum"), fundos_com_captacao=("_pos", "sum"), delta_cotistas=("delta_cotistas", "sum"))
        g["pct_pl"] = np.where(g.pl_inicial > 0, g.capt_liquida / g.pl_inicial * 100, np.nan)
        return g

    L["pl_atual"] = L.cnpj.map(attrs.set_index("cnpj").pl_atual)
    universos = {"todos": L, "sem_exclusivos": L[~L.exclusivo]}
    gj, gc = [], []
    for nome, df in universos.items():
        a = agrega(df, ["gestora", "janela", "data_base"])
        pl = df[df.janela == jn[0]].groupby("gestora").pl_atual.sum()
        a.insert(3, "pl_atual", a.gestora.map(pl))
        a.insert(0, "universo", nome)
        gj.append(a)
        b = agrega(df, ["gestora", "classe_anbima", "janela", "data_base"])
        b.insert(0, "universo", nome)
        gc.append(b)
    GJ = pd.concat(gj, ignore_index=True)
    ex.salvar("captacao_gestoras_janelas", GJ, "Captação por gestora em cada janela (formato longo). universo=todos | sem_exclusivos. Só fundos com PL inicial>0 entram na captação.", "Captação · gestoras")
    rk = []
    for nome in universos:
        d = GJ[GJ.universo == nome]
        w = d.pivot(index="gestora", columns="janela", values=["capt_liquida", "pct_pl"])
        w.columns = [f"{a}_{b}" for a, b in w.columns]
        w = w[[f"{a}_{j}" for a in ("capt_liquida", "pct_pl") for j in jn]]
        d0 = d[d.janela == jn[0]].set_index("gestora")
        w.insert(0, "pl_atual", d0.pl_atual)
        w.insert(0, "n_fundos", d0.n_fundos)
        w["share_pl_pct"] = w.pl_atual / w.pl_atual.sum() * 100
        w.insert(0, "universo", nome)
        rk.append(w.reset_index())
    ex.salvar("captacao_gestoras_ranking", pd.concat(rk, ignore_index=True), "Ranking de gestoras em formato largo: captação líquida e % PL em todas as janelas (universo todos | sem_exclusivos).", "Captação · gestoras")
    ex.salvar("captacao_gestoras_classe_janelas", pd.concat(gc, ignore_index=True), "Captação por gestora × classe ANBIMA × janela.", "Captação · gestoras")

    FMg = FM.merge(attrs[["cnpj", "gestora", "exclusivo"]], on="cnpj")
    gm = []
    for un, d in (("todos", FMg), ("sem_exclusivos", FMg[~FMg.exclusivo])):
        a = d.groupby(["gestora", "mes"], as_index=False).agg(capt_liquida=("capt_liquida", "sum"), pl_inicio_mes=("pl_inicio_mes", "sum"))
        a["pct_pl"] = np.where(a.pl_inicio_mes > 0, a.capt_liquida / a.pl_inicio_mes * 100, np.nan)
        a.insert(0, "universo", un)
        gm.append(a)
    ex.salvar("captacao_gestoras_mensal", pd.concat(gm, ignore_index=True), "Captação líquida mensal por gestora.", "Captação · gestoras")
    FDg = FD.merge(attrs[["cnpj", "gestora", "exclusivo"]], on="cnpj")
    gd = []
    for un, d in (("todos", FDg), ("sem_exclusivos", FDg[~FDg.exclusivo])):
        a = d.groupby(["gestora", "data"], as_index=False).agg(capt_liquida=("capt_liquida", "sum"))
        a.insert(0, "universo", un)
        gd.append(a)
    ex.salvar("captacao_gestoras_diaria", pd.concat(gd, ignore_index=True), f"Captação líquida diária por gestora nos últimos {N_DIARIO} pregões.", "Captação · gestoras")


def main():
    cad = ler_cadastro()
    inf = ler_informe(set(cad.cnpj))
    inf = inf.drop_duplicates()  # reapresentacoes identicas

    # cota: subclasse de maior PL do dia (proxy da cota da classe)
    cota = inf.sort_values("VL_PATRIM_LIQ", ascending=False).drop_duplicates(["cnpj", "DT_COMPTC"])
    g = inf.groupby(["cnpj", "DT_COMPTC"], as_index=False).agg(
        PL=("VL_PATRIM_LIQ", "sum"), CAP=("CAPTC_DIA", "sum"), RES=("RESG_DIA", "sum"), COT=("NR_COTST", "sum"))

    def piv(df, col):
        return df.pivot(index="cnpj", columns="DT_COMPTC", values=col)

    PL, CAP, RES, COT = (piv(g, c) for c in ["PL", "CAP", "RES", "COT"])
    Q = piv(cota, "VL_QUOTA")
    datas = list(PL.columns)  # strings ISO ja ordenadas
    datas = sorted(datas)
    PL, CAP, RES, COT, Q = (x.reindex(columns=datas) for x in (PL, CAP, RES, COT, Q))
    last = len(datas) - 1
    print("periodo", datas[0], "->", datas[-1], "| fundos com dados:", len(PL))

    PLf, Qf, COTf = PL.ffill(axis=1), Q.ffill(axis=1), COT.ffill(axis=1)
    NET = (CAP.fillna(0) - RES.fillna(0))
    CAPf, RESf = CAP.fillna(0), RES.fillna(0)

    # universo: reportou nos ultimos 5 pregoes e PL > 0
    recente = PL.iloc[:, -5:].notna().any(axis=1) & (PLf.iloc[:, -1] > 0)
    ids = PL.index[recente]
    print("universo ativo:", len(ids))
    PLf, Qf, COTf, NET, CAPf, RESf = (x.loc[ids] for x in (PLf, Qf, COTf, NET, CAPf, RESf))

    ult = datas[-1]
    ano, mes = int(ult[:4]), int(ult[5:7])

    def idx_antes(prefixo):
        """indice do ultimo pregao com data < prefixo (ex: '2026-11')."""
        k = [i for i, d in enumerate(datas) if d < prefixo]
        return k[-1] if k else None

    bases = []
    for nome, n in JANELAS:
        if n:
            bases.append(max(last - n, 0))
        elif nome == "MTD":
            bases.append(idx_antes(f"{ano}-{mes:02d}") or 0)
        else:
            bases.append(idx_antes(f"{ano}-01") or 0)

    def janela(b):
        sl = slice(b + 1, last + 1)
        return dict(
            F=NET.iloc[:, sl].sum(axis=1), C=CAPf.iloc[:, sl].sum(axis=1), R=RESf.iloc[:, sl].sum(axis=1),
            P0=PLf.iloc[:, b], DC=COTf.iloc[:, last] - COTf.iloc[:, b],
            RT=(Qf.iloc[:, last] / Qf.iloc[:, b] - 1) * 100)

    JW = [janela(b) for b in bases]

    # serie mensal (ultimos 12 meses fechados + mes corrente)
    meses = sorted({d[:7] for d in datas})
    if len(meses) > 13:
        meses = meses[-13:]
    MF, MP = [], []
    for m in meses:
        b = idx_antes(m)
        if b is None:
            b = 0
        idxs = [i for i, d in enumerate(datas) if d[:7] == m]
        MF.append(NET.iloc[:, idxs[0]:idxs[-1] + 1].sum(axis=1))
        MP.append(PLf.iloc[:, b])
    DIA = NET.iloc[:, -N_DIARIO:]

    def r(x, nd=1):
        return None if (x is None or not np.isfinite(x)) else round(float(x), nd)

    def mil(x):
        return r(x / 1e3, 1)

    cad = cad.set_index("cnpj")
    out = []
    for cnpj in ids:
        c = cad.loc[cnpj]
        out.append({
            "id": fmt_cnpj(cnpj), "n": c.Denominacao_Social,
            "a": (c.Classificacao_Anbima if isinstance(c.Classificacao_Anbima, str) else "Sem classificacao"),
            "pa": c.Publico_Alvo if isinstance(c.Publico_Alvo, str) else "n/d",
            "ex": c.Exclusivo == "S", "fc": c.Classe_Cotas if isinstance(c.Classe_Cotas, str) else "n/d",
            "co": c.Forma_Condominio if isinstance(c.Forma_Condominio, str) else "n/d",
            "g": c.Gestor if isinstance(c.Gestor, str) else "n/d",
            "ad": c.Administrador if isinstance(c.Administrador, str) else "n/d",
            "ini": c.Data_Inicio if isinstance(c.Data_Inicio, str) else None,
            "pl": mil(PLf.loc[cnpj].iloc[-1]), "nc": int(COTf.loc[cnpj].iloc[-1]) if np.isfinite(COTf.loc[cnpj].iloc[-1]) else None,
            "F": [mil(w["F"][cnpj]) for w in JW], "C": [mil(w["C"][cnpj]) for w in JW],
            "R": [mil(w["R"][cnpj]) for w in JW], "P0": [mil(w["P0"][cnpj]) for w in JW],
            "DC": [r(w["DC"][cnpj], 0) for w in JW], "RT": [r(w["RT"][cnpj], 2) for w in JW],
            "MF": [mil(s[cnpj]) for s in MF], "MP": [mil(s[cnpj]) for s in MP],
            "D": [mil(v) for v in DIA.loc[cnpj].values],
        })

    print("exportando tabelas da captação…")
    exportar_captacao(cad, ids, PLf, COTf, JW, bases, datas, meses, MF, MP, DIA)

    meta = {"ultima": ult, "janelas": [j[0] for j in JANELAS], "meses": meses, "datas_diarias": datas[-N_DIARIO:],
            "bases": [datas[b] for b in bases], "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}
    payload = json.dumps({"meta": meta, "fundos": out}, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DADOS__*/null", payload)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(html, encoding="utf-8")
    print(f"ok -> {SAIDA}  ({SAIDA.stat().st_size/1e6:.1f} MB, {len(out)} fundos, ate {ult})")


if __name__ == "__main__":
    main()
