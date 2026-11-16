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

    meta = {"ultima": ult, "janelas": [j[0] for j in JANELAS], "meses": meses, "datas_diarias": datas[-N_DIARIO:],
            "bases": [datas[b] for b in bases], "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}
    payload = json.dumps({"meta": meta, "fundos": out}, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DADOS__*/null", payload)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(html, encoding="utf-8")
    print(f"ok -> {SAIDA}  ({SAIDA.stat().st_size/1e6:.1f} MB, {len(out)} fundos, ate {ult})")


if __name__ == "__main__":
    main()
