"""Painel CVM unico: atualiza tudo e junta Monitor de Captacao + Publicacoes em um so HTML.

Uso:
    python painel.py              # baixa, processa os dois relatorios e gera painel_cvm.html
    python painel.py --so-juntar  # apenas recombina os HTMLs ja gerados
"""
import argparse
import html
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).parent
ABAS = [("Captação Multimercado", AQUI / "data" / "tmp" / "monitor_captacao.html"),
        ("Publicações CVM", AQUI / "data" / "tmp" / "publicacoes_cvm.html")]
SAIDA = AQUI / "painel_cvm.html"

SHELL = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel CVM</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--line:#e3e6ec;--acc:#cc092f;--chip:#eef0f4}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--ink:#e8ebf0;--line:#272d38;--acc:#ff4d6d;--chip:#222833}}
html,body{height:100%;margin:0}body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font:14px system-ui,Segoe UI,sans-serif}
nav{display:flex;gap:4px;padding:8px 14px 0;background:var(--card);border-bottom:1px solid var(--line)}
nav b{align-self:center;margin-right:14px;font-size:15px}
nav button{border:1px solid var(--line);border-bottom:0;background:var(--chip);color:var(--ink);padding:8px 16px;border-radius:8px 8px 0 0;cursor:pointer;font:inherit}
nav button.on{background:var(--bg);color:var(--acc);font-weight:600}
iframe{flex:1;border:0;width:100%;background:var(--bg);display:none}iframe.on{display:block}
</style></head><body>
<nav><b>Painel CVM</b>__BOTOES__</nav>
__FRAMES__
<script>
function go(i){document.querySelectorAll('nav button').forEach((b,k)=>b.classList.toggle('on',k===i));
document.querySelectorAll('iframe').forEach((f,k)=>f.classList.toggle('on',k===i));try{localStorage.setItem('painel',i)}catch(e){}}
let s=0;try{s=+localStorage.getItem('painel')||0}catch(e){}go(s);
</script></body></html>"""


def juntar():
    import exportar
    pg = AQUI / "data" / "tmp" / "exportacoes.html"
    pg.write_text(exportar.pagina_html(), encoding="utf-8")
    leiame = AQUI / "EXPORTACOES.md"
    if leiame.exists():
        (AQUI / "exportacoes").mkdir(exist_ok=True)
        shutil.copy(leiame, AQUI / "exportacoes" / "README.md")
    abas = ABAS + [("Exportações", pg)]
    botoes = "".join(f'<button onclick="go({i})">{html.escape(n)}</button>' for i, (n, _) in enumerate(abas))
    frames = "".join(f'<iframe title="{html.escape(n)}" srcdoc="{html.escape(p.read_text(encoding="utf-8"), quote=True)}"></iframe>'
                     for n, p in abas)
    SAIDA.write_text(SHELL.replace("__BOTOES__", botoes).replace("__FRAMES__", frames), encoding="utf-8")
    print(f"ok -> {SAIDA} ({SAIDA.stat().st_size/1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-juntar", action="store_true")
    a = ap.parse_args()
    if not a.so_juntar:
        for script in ["baixar_cvm.py", "monitor.py", "publicacoes.py"]:
            print(f"\n== {script}")
            subprocess.run([sys.executable, str(AQUI / script)], check=True, cwd=AQUI)
    juntar()


if __name__ == "__main__":
    main()
