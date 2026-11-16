"""Baixa (com cache) os dados abertos da CVM usados no Monitor de Captacao.

Uso:  python baixar_cvm.py [--meses 15] [--forcar]
Saida: data/raw/inf_diario/*.zip  e  data/raw/reg/*.csv
"""
import argparse
import datetime as dt
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://dados.cvm.gov.br/dados/FI"
RAIZ = Path(__file__).parent / "data" / "raw"
UA = {"User-Agent": "monitor-captacao/1.0"}


def baixar(url: str, destino: Path, forcar=False, reaproveitar_horas=None) -> bool:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not forcar:
        if reaproveitar_horas is None:
            return False  # arquivo fechado (mes passado): cache vale para sempre
        idade = (dt.datetime.now().timestamp() - destino.stat().st_mtime) / 3600
        if idade < reaproveitar_horas:
            return False
    req = urllib.request.Request(url, headers=UA)
    tmp = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(destino)
    return True


def meses_alvo(n: int):
    hoje = dt.date.today()
    y, m = hoje.year, hoje.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=15)
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()

    # cadastro novo (RCVM 175): renovar a cada 12h
    z = RAIZ / "reg" / "registro_fundo_classe.zip"
    if baixar(f"{BASE}/CAD/DADOS/registro_fundo_classe.zip", z, a.forcar, 12):
        print("cadastro baixado")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(RAIZ / "reg")

    atual = meses_alvo(1)[0]
    for ym in meses_alvo(a.meses):
        d = RAIZ / "inf_diario" / f"inf_diario_fi_{ym}.zip"
        try:
            # mes corrente/anterior mudam (reapresentacoes): renovar a cada 6h
            recente = ym >= meses_alvo(2)[0]
            novo = baixar(f"{BASE}/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ym}.zip", d,
                          a.forcar, 6 if recente else None)
            print(("baixado " if novo else "cache   ") + d.name)
        except Exception as e:  # mes ainda inexistente etc.
            print(f"falhou {ym}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
