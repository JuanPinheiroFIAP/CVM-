"""Servidor local do Painel CVM.

Serve o painel em http://127.0.0.1:8765/ e abre os documentos da CVM (rad.cvm.gov.br),
que no navegador direto aparecem em branco: o servidor busca o arquivo e o entrega ao navegador.

Uso: python servidor.py [--sem-navegador]
"""
import argparse
import http.client
import mimetypes
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).parent
HOST, PORT = "127.0.0.1", 8765
HOSTS_OK = {"www.rad.cvm.gov.br", "rad.cvm.gov.br", "fnet.bmfbovespa.com.br", "web.cvm.gov.br"}  # so documentos da CVM/B3
UA = "curl"  # o RAD só entrega o arquivo para clientes que não são navegadores


def e_casca(corpo):
    """Página em branco do RAD ("ENET Download de Documento") que o servidor devolve de forma intermitente."""
    return b"ENET Download de Documento" in corpo[:6000] and corpo[:4] != b"%PDF" and len(corpo) < 30000


def buscar(url, tentativas=12):
    # O RAD alterna entre entregar o arquivo e uma página em branco; repetir até vir o arquivo.
    ult = RuntimeError("a CVM devolveu página em branco")
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo, cab = r.read(), r.headers
            if not e_casca(corpo):
                return corpo, cab
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            ult = e
        time.sleep(0.4)
    raise ult


def tipo(corpo, cab):
    nome = ""
    m = re.search(r'filename="?([^";]+)', cab.get("Content-Disposition") or "")
    if m:
        nome = m.group(1)
    if corpo[:4] == b"%PDF":
        return "application/pdf", nome or "documento.pdf"
    if corpo[:2] == b"PK":
        return "application/zip", nome or "documento.zip"
    if corpo[:200].lstrip().lower().startswith((b"<!doctype html", b"<html", b"<?xml")):
        return "text/html; charset=utf-8", nome
    ct = mimetypes.guess_type(nome)[0] if nome else None
    return ct or "application/octet-stream", nome


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ct="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/painel", "/painel_cvm.html"):
            f = AQUI / "painel_cvm.html"
            if not f.exists():
                return self._send(404, "painel_cvm.html não encontrado: rode atualizar.bat".encode())
            return self._send(200, f.read_bytes())
        if u.path.startswith("/exportacoes/"):
            rel = urllib.parse.unquote(u.path[len("/exportacoes/"):])
            partes = rel.split("/")
            if not partes or any(not re.fullmatch(r"[\w\-.]+", p) or p in (".", "..") for p in partes):
                return self._send(400, "caminho inválido".encode())
            f = AQUI / "exportacoes"
            for p in partes:
                f = f / p
            if not f.is_file():
                return self._send(404, "arquivo não encontrado: rode atualizar.bat".encode())
            nome = partes[-1]
            ct = {"csv": "text/csv; charset=utf-8", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  "parquet": "application/octet-stream", "json": "application/json", "md": "text/markdown; charset=utf-8"}.get(
                f.suffix.lstrip("."), "application/octet-stream")
            return self._send(200, f.read_bytes(), ct, {"Content-Disposition": f'attachment; filename="{nome}"'})
        if u.path == "/doc":
            alvo = urllib.parse.parse_qs(u.query).get("u", [""])[0]
            p = urllib.parse.urlparse(alvo)
            if p.scheme != "https" or p.hostname not in HOSTS_OK:
                return self._send(400, "endereço não permitido".encode())
            try:
                corpo, cab = buscar(alvo)
            except Exception as e:
                return self._send(502, f"Não consegui buscar o documento na CVM ({e}). Tente de novo.".encode())
            ct, nome = tipo(corpo, cab)
            extra = {"Content-Disposition": f'inline; filename="{nome}"'} if nome else {}
            return self._send(200, corpo, ct, extra)
        self._send(404, b"nao encontrado")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args()
    try:
        srv = ThreadingHTTPServer((HOST, PORT), H)
    except OSError:  # porta ocupada: provavelmente o servidor já está rodando
        print(f"Servidor já ativo em http://{HOST}:{PORT}/")
        if not a.sem_navegador:
            webbrowser.open(f"http://{HOST}:{PORT}/")
        return
    print(f"Painel em http://{HOST}:{PORT}/  (feche esta janela para encerrar)")
    if not a.sem_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
