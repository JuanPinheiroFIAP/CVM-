"""Painel de Publicacoes CVM: Fatos Relevantes, Recompras, Assembleias e Composicao de Carteira.

Uso:
    python publicacoes.py [--dias 365] [--min-pl 20] [--top 40]

Fontes (dados.cvm.gov.br):
  - CIA_ABERTA/DOC/IPE   -> fatos relevantes, assembleias e recompras das companhias abertas
  - FI/DOC/EVENTUAL      -> fatos relevantes e assembleias dos fundos
  - FI/DOC/CDA           -> composicao de carteira dos fundos (multimercado, nao exclusivos)
Saida: publicacoes_cvm.html (autocontido; os links abrem o documento no portal da CVM).
"""
import argparse
import datetime as dt
import json
import re
import urllib.error
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from baixar_cvm import BASE, RAIZ, baixar

AQUI = Path(__file__).parent
TEMPLATE = AQUI / "publicacoes_template.html"
SAIDA = AQUI / "data" / "tmp" / "publicacoes_cvm.html"
RE_RECOMPRA = re.compile(
    r"recompra|aquisi[cç][aã]o de a[cç][oõ]es de (sua )?emiss[aã]o|a[cç][oõ]es de (sua )?pr[oó]pria emiss|"
    r"a[cç][oõ]es em tesouraria|negocia[cç][aã]o de a[cç][oõ]es de pr[oó]pria|programa de aquisi|"
    r"cancelamento de a[cç][oõ]es", re.I)
RE_NAO_RECOMPRA = re.compile(r"oferta p[uú]blica de aquisi|\bOPA\b", re.I)


def s(v):
    return v if isinstance(v, str) else ""


def ler_ipe(anos, desde):
    partes = []
    for a in anos:
        z = RAIZ / "ipe" / f"ipe_cia_aberta_{a}.zip"
        try:
            baixar(f"{BASE.replace('/FI', '')}/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{a}.zip", z, False, 6 if a == dt.date.today().year else None)
        except Exception as e:
            print("IPE", a, "falhou:", e)
            continue
        partes.append(pd.read_csv(z, sep=";", encoding="latin1", dtype=str))
    d = pd.concat(partes, ignore_index=True)
    d["Versao_n"] = pd.to_numeric(d.Versao, errors="coerce").fillna(0)
    d = d.sort_values("Versao_n").drop_duplicates("Protocolo_Entrega", keep="last")
    d = d[d.Data_Entrega >= desde].sort_values("Data_Entrega", ascending=False)
    return d


def linhas_ipe(d):
    def mk(x):
        return [x.Data_Entrega, x.Data_Referencia, x.Nome_Companhia, x.CNPJ_Companhia, x.Categoria,
                s(x.Tipo), s(x.Especie), s(x.Assunto), s(x.Link_Download)]
    fr = [mk(x) for x in d[d.Categoria == "Fato Relevante"].itertuples()]
    ass = [mk(x) for x in d[d.Categoria == "Assembleia"].itertuples()]
    txt = d.Assunto.fillna("") + " " + d.Especie.fillna("")
    mr = txt.map(lambda t: bool(RE_RECOMPRA.search(t)) and not RE_NAO_RECOMPRA.search(t))
    mr &= ~d.Categoria.isin(["Valores Mobiliários negociados e detidos (art. 11 da Instr. CVM nº 358)"])
    rec = [mk(x) for x in d[mr].itertuples()]
    return fr, ass, rec


def ler_fundos_eventual(anos, desde):
    partes = []
    for a in anos:
        z = RAIZ / "ipe" / f"eventual_fi_{a}.csv"
        try:
            baixar(f"{BASE}/DOC/EVENTUAL/DADOS/eventual_fi_{a}.csv", z, False, 6 if a == dt.date.today().year else None)
        except Exception as e:
            print("EVENTUAL", a, "falhou:", e)
            continue
        partes.append(pd.read_csv(z, sep=";", encoding="latin1", dtype=str))
    d = pd.concat(partes, ignore_index=True)
    tipos = {"FATO RELEV": "Fato relevante", "AGO": "AGO (ata)", "EDITAL AGO": "AGO (edital)",
             "AGE PROPOST ADM": "AGE (proposta)", "AGO PROPOST ADM": "AGO (proposta)",
             "AGO/AGE PROPADM": "AGO/AGE (proposta)", "PROPOSTA ADMINI": "Proposta da administração",
             "AED": "Assembleia (AED)", "AID": "Assembleia (AID)"}
    d = d[d.TP_DOC.isin(tipos) & (d.DT_RECEB >= desde)].copy()
    d = d[~d.TP_DOC.isin(["AID", "AED"])]  # AID/AED sao informes do administrador, nao assembleias
    d["T"] = d.TP_DOC.map(tipos)
    d = d.sort_values("DT_RECEB", ascending=False)
    fr = [[x.DT_RECEB, s(x.DT_COMPTC), s(x.DENOM_SOCIAL), s(x.CNPJ_FUNDO_CLASSE), x.T, s(x.LINK_ARQ)] for x in d.itertuples()]
    return fr


def ultimos_cda(n=2):
    achados = []
    hoje = dt.date.today()
    y, m = hoje.year, hoje.month
    for _ in range(8):
        ym = f"{y}{m:02d}"
        z = RAIZ / "cda" / f"cda_fi_{ym}.zip"
        try:
            baixar(f"{BASE}/DOC/CDA/DADOS/cda_fi_{ym}.zip", z, False, 12 if len(achados) == 0 else None)
            achados.append((ym, z))
        except urllib.error.HTTPError:
            pass
        if len(achados) == n:
            break
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return achados  # [(mais recente), (anterior)]


def rotulo(df):
    def col(n):
        return df[n].fillna("") if n in df.columns else pd.Series("", index=df.index)
    nome = col("DS_ATIVO")
    for alt in ["CD_ATIVO", "NM_FUNDO_CLASSE_SUBCLASSE_COTA", "DS_ATIVO_EXTERIOR", "EMISSOR"]:
        nome = nome.where(nome != "", col(alt))
    nome = nome.where(nome != "", col("TP_TITPUB"))
    extra = col("DT_VENC").where(col("DT_VENC") == "", " (venc " + col("DT_VENC") + ")")
    return (col("TP_ATIVO") + " · " + nome + extra).str.strip(" ·")


def ler_cda(zpath, ym, cnpjs):
    out, pl = [], None
    with zipfile.ZipFile(zpath) as z:
        pl = pd.read_csv(z.open(f"cda_fi_PL_{ym}.csv"), sep=";", encoding="latin1", dtype=str)
        pl["cnpj"] = pl.CNPJ_FUNDO_CLASSE.str.replace(r"\D", "", regex=True)
        pl["PL"] = pd.to_numeric(pl.VL_PATRIM_LIQ, errors="coerce")
        pl = pl[pl.cnpj.isin(cnpjs)].groupby("cnpj").PL.sum()
        for b in [1, 2, 4, 5, 6, 7, 8]:
            n = f"cda_fi_BLC_{b}_{ym}.csv"
            if n not in z.namelist():
                continue
            d = pd.read_csv(z.open(n), sep=";", encoding="latin1", dtype=str)
            d["cnpj"] = d.CNPJ_FUNDO_CLASSE.str.replace(r"\D", "", regex=True)
            d = d[d.cnpj.isin(cnpjs)].copy()
            if d.empty:
                continue
            d["V"] = pd.to_numeric(d.VL_MERC_POS_FINAL, errors="coerce")
            d["Q"] = pd.to_numeric(d.QT_POS_FINAL, errors="coerce")
            d["ativo"] = rotulo(d)
            d["bl"] = d.TP_APLIC.fillna("Outros")
            out.append(d[["cnpj", "bl", "ativo", "V", "Q"]])
    pos = pd.concat(out, ignore_index=True)
    pos = pos.groupby(["cnpj", "bl", "ativo"], as_index=False).agg(V=("V", "sum"), Q=("Q", "sum"))
    return pl, pos


def montar_carteiras(min_pl, topn):
    cl = pd.read_csv(RAIZ / "reg" / "registro_classe.csv", sep=";", encoding="latin1", dtype=str)
    cl = cl[(cl.Classificacao == "Multimercado") & (cl.Situacao == "Em Funcionamento Normal") & (cl.Exclusivo != "S")].copy()
    cl["cnpj"] = cl.CNPJ_Classe.str.replace(r"\D", "", regex=True)
    cl = cl.drop_duplicates("cnpj").set_index("cnpj")
    cda = ultimos_cda(2)
    if not cda:
        return [], {}
    (ym1, z1) = cda[0]
    pl1, pos1 = ler_cda(z1, ym1, set(cl.index))
    ym0 = None
    pos0 = pl0 = None
    if len(cda) > 1:
        ym0, z0 = cda[1]
        pl0, pos0 = ler_cda(z0, ym0, set(cl.index))
    ids = pl1[pl1 >= min_pl * 1e6].index
    pos1 = pos1[pos1.cnpj.isin(ids)]
    prev = {}
    if pos0 is not None:
        p0 = pos0[pos0.cnpj.isin(ids)].copy()
        p0["pct"] = p0.V / p0.cnpj.map(pl0) * 100
        p0 = p0[np.isfinite(p0.pct)]
        prev = {(r.cnpj, r.bl, r.ativo): r.pct for r in p0.itertuples()}
        blocos0 = p0.groupby(["cnpj", "bl"]).pct.sum()
    pos1 = pos1.assign(pct=pos1.V / pos1.cnpj.map(pl1) * 100)
    pos1 = pos1[np.isfinite(pos1.pct)]
    blocos1 = pos1.groupby(["cnpj", "bl"]).pct.sum()
    fundos = []
    for cnpj, g in pos1.groupby("cnpj"):
        g = g.reindex(g.pct.abs().sort_values(ascending=False).index)
        c = cl.loc[cnpj]
        top = []
        for r in g.head(topn).itertuples():
            ant = prev.get((r.cnpj, r.bl, r.ativo))
            top.append([r.bl, r.ativo, round(r.V / 1e3, 1), round(r.pct, 2), None if ant is None else round(r.pct - ant, 2)])
        bl = {k: round(v, 2) for k, v in blocos1.loc[cnpj].items()}
        bl0 = {k: round(v, 2) for k, v in blocos0.loc[cnpj].items()} if pos0 is not None and cnpj in blocos0.index.get_level_values(0) else {}
        d = cnpj.zfill(14)
        fundos.append({"id": f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}", "n": c.Denominacao_Social,
                       "a": s(c.Classificacao_Anbima) or "Sem classificação", "pl": round(float(pl1[cnpj]) / 1e6, 1),
                       "np": int(len(g)), "bl": bl, "bl0": bl0, "top": top})
    fundos.sort(key=lambda f: -f["pl"])
    return fundos, {"mes": ym1, "mes_ant": ym0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=365)
    ap.add_argument("--min-pl", type=float, default=20, help="PL minimo (R$ mi) dos fundos na aba Carteira")
    ap.add_argument("--top", type=int, default=40, help="posicoes por fundo na aba Carteira")
    a = ap.parse_args()
    hoje = dt.date.today()
    desde = (hoje - dt.timedelta(days=a.dias)).isoformat()
    anos = sorted({hoje.year, (hoje - dt.timedelta(days=a.dias)).year})

    ipe = ler_ipe(anos, desde)
    fr, ass, rec = linhas_ipe(ipe)
    print(f"IPE: {len(ipe)} docs | FR {len(fr)} | Assembleias {len(ass)} | Recompras {len(rec)} | ate {ipe.Data_Entrega.max()}")
    ffr = ler_fundos_eventual(anos, desde)
    print("Fundos (FR/assembleias):", len(ffr))
    cart, mcda = montar_carteiras(a.min_pl, a.top)
    print("Carteiras:", len(cart), mcda)

    # CSVs prontos para Excel / Power BI (pasta saidas/)
    out = AQUI / "saidas"
    out.mkdir(exist_ok=True)
    cols_ipe = ["Data_Entrega", "Data_Referencia", "Empresa", "CNPJ", "Categoria", "Tipo", "Especie", "Assunto", "Link"]
    for nome, linhas, cols in [("fatos_relevantes", fr, cols_ipe), ("recompras", rec, cols_ipe), ("assembleias", ass, cols_ipe),
                               ("fundos_fr_assembleias", ffr, ["Recebido", "Competencia", "Fundo", "CNPJ", "Tipo", "Link"])]:
        pd.DataFrame(linhas, columns=cols).to_csv(out / f"{nome}.csv", sep=";", index=False, encoding="utf-8-sig")
    pd.DataFrame([[f["n"], f["id"], f["a"], f["pl"], *t] for f in cart for t in f["top"]],
                 columns=["Fundo", "CNPJ", "ANBIMA", "PL_R$mi", "Tipo", "Ativo", "Valor_R$mil", "Pct_PL", "Delta_pp"]
                 ).to_csv(out / "carteiras.csv", sep=";", index=False, encoding="utf-8-sig", decimal=",")
    print("CSVs em", out)

    meta = {"gerado": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "desde": desde, "ate_ipe": ipe.Data_Entrega.max(), **mcda}
    payload = json.dumps({"meta": meta, "fr": fr, "ass": ass, "rec": rec, "ffr": ffr, "cart": cart},
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DADOS__*/null", payload), encoding="utf-8")
    print(f"ok -> {SAIDA} ({SAIDA.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
