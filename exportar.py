"""Exportação dos dados do painel em CSV, Excel (.xlsx) e Parquet.

Cada tabela do painel vira três arquivos em exportacoes/ e é registrada em
exportacoes/_catalogo.json (usado pela aba "Exportações" do painel).

CSV: separador ';', decimal ',' e UTF-8 com BOM (abre direto no Excel em português).
Parquet: tipos nativos (datas, números, booleanos) - ideal para Python, Power BI, DuckDB, etc.
"""
import datetime as dt
import html
import json
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
SAIDA = AQUI / "exportacoes"
CATALOGO = SAIDA / "catalogo.json"
LIMITE_XLSX = 1_048_575


def _catalogo():
    try:
        return json.loads(CATALOGO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar(nome, df, descricao, grupo, pasta=""):
    """Grava df como CSV, XLSX e Parquet em exportacoes/<pasta>/ e registra no catálogo.

    pasta organiza os arquivos por domínio (ex.: "captacao/gestoras") para quem consome
    a pasta exportacoes/ de fora deste projeto. Vazio = raiz de exportacoes/.
    """
    destino = (SAIDA / pasta) if pasta else SAIDA
    destino.mkdir(parents=True, exist_ok=True)
    df = df.reset_index(drop=True)
    df.to_parquet(destino / f"{nome}.parquet", index=False, compression="snappy")
    df.to_csv(destino / f"{nome}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    xlsx = len(df) <= LIMITE_XLSX
    if xlsx:
        with pd.ExcelWriter(destino / f"{nome}.xlsx", engine="xlsxwriter",
                            datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as w:
            df.to_excel(w, sheet_name=nome[:31], index=False)
            ws = w.sheets[nome[:31]]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
            for i, c in enumerate(df.columns):
                amostra = df[c].head(300).astype(str).str.len()
                ws.set_column(i, i, min(max(len(str(c)), int(amostra.max()) if len(amostra) else 8) + 2, 60))
    elif (destino / f"{nome}.xlsx").exists():
        (destino / f"{nome}.xlsx").unlink()
    cat = _catalogo()
    chave = f"{pasta}/{nome}" if pasta else nome
    cat[chave] = {"nome": nome, "pasta": pasta, "descricao": descricao, "grupo": grupo, "linhas": int(len(df)),
                  "colunas": [str(c) for c in df.columns], "xlsx": xlsx, "gerado": dt.datetime.now().strftime("%d/%m/%Y %H:%M")}
    CATALOGO.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  exportado {chave}: {len(df):,} linhas".replace(",", "."))


def fmt(n):
    return f"{n:,}".replace(",", ".")


def pagina_html():
    """HTML da aba 'Exportações' (links servidos por servidor.py em /exportacoes/)."""
    cat = _catalogo()
    grupos = {}
    for chave, c in cat.items():
        grupos.setdefault(c["grupo"], []).append((chave, c))
    linhas = []
    for g, itens in grupos.items():
        linhas.append(f'<tr class="g"><td colspan="5">{html.escape(g)}</td></tr>')
        for chave, c in sorted(itens):
            nome = c.get("nome", chave)
            cols = ", ".join(c["colunas"][:14]) + (" …" if len(c["colunas"]) > 14 else "")
            xl = (f'<a href="/exportacoes/{chave}.xlsx" download>Excel</a>' if c["xlsx"]
                  else '<span class="mut" title="acima do limite de linhas do Excel">Excel n/d</span>')
            linhas.append(
                f'<tr><td><b>{html.escape(nome)}</b><div class="mut">{html.escape(c["descricao"])}</div>'
                f'<details><summary>colunas ({len(c["colunas"])})</summary><div class="mut">{html.escape(cols)}</div></details></td>'
                f'<td class="n">{fmt(c["linhas"])}</td><td class="act"><a href="/exportacoes/{chave}.csv" download>CSV</a></td>'
                f'<td class="act">{xl}</td><td class="act"><a href="/exportacoes/{chave}.parquet" download>Parquet</a></td></tr>')
    corpo = "\n".join(linhas)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Exportações</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mut:#5d6675;--line:#e3e6ec;--acc:#cc092f;--chip:#eef0f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1218;--card:#171b23;--ink:#e8ebf0;--mut:#9aa4b5;--line:#272d38;--acc:#ff4d6d;--chip:#222833}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,Segoe UI,sans-serif;padding:16px 20px}}
h1{{font-size:18px;margin:0 0 6px}}.mut{{color:var(--mut);font-size:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-top:12px}}
table{{border-collapse:collapse;width:100%}}td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
tr.g td{{background:var(--chip);font-weight:700;color:var(--acc)}}td.n{{text-align:right;white-space:nowrap}}td.act{{white-space:nowrap;text-align:center}}
a{{color:var(--acc);text-decoration:none;font-weight:600}}a:hover{{text-decoration:underline}}
details summary{{cursor:pointer;color:var(--mut);font-size:12px}}
#aviso{{display:none;background:#fff3cd;color:#5a4500;padding:10px 12px;border-radius:8px;margin-top:10px}}
</style></head><body>
<h1>Exportações</h1>
<div class="mut">Todos os dados do painel, completos (sem os filtros da tela), em <b>CSV</b> (separador “;”, decimal “,”, abre no Excel), <b>Excel</b> e <b>Parquet</b> (tipos nativos, para Python/Power BI/DuckDB). Os arquivos ficam organizados por pasta em <code>exportacoes/</code> (captacao/fundos, captacao/gestoras, publicacoes, carteiras). Valores em R$ (reais), exceto onde a coluna indicar. Pra consumir de outro projeto: <code>exportacoes/README.md</code> tem o dicionário de dados (grão, chave, convenções) e <code>exportacoes/catalogo.json</code> lista as tabelas com descrição e colunas, programaticamente.</div>
<div id="aviso">Os downloads só funcionam com o painel aberto pelo servidor local (<b>atualizar.bat</b> ou <b>abrir_painel.bat</b>). Fora dele, pegue os arquivos direto na pasta <code>exportacoes/</code>.</div>
<div class="card"><table>{corpo}</table></div>
<script>try{{if(!/^https?:$/.test(window.top.location.protocol)) document.getElementById('aviso').style.display='block';}}catch(e){{}}</script>
</body></html>"""
