"""Atualização diária e sem interação do Painel CVM (para o Agendador de Tarefas).

Baixa os dados novos da CVM, regenera as tabelas (exportacoes/) e o painel_cvm.html.
Não abre navegador nem servidor. Registra tudo em logs/atualizacao_AAAA-MM-DD.log.

Código de saída: 0 = ok (ou já havia uma atualização em andamento) | 1 = falhou (veja o log).
Uso:  python atualizar_diario.py
"""
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).parent
LOGS = AQUI / "logs"
LOCK = AQUI / "data" / ".atualizando.lock"
LOCK_MAX_H = 4          # lock mais velho que isso é considerado abandonado (execução anterior morreu)
TIMEOUT_H = 3           # tempo máximo de uma atualização
GUARDAR_LOGS_DIAS = 30


def log(f, msg):
    linha = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(linha)
    f.write(linha + "\n")
    f.flush()


def main():
    LOGS.mkdir(exist_ok=True)
    LOCK.parent.mkdir(exist_ok=True)
    arq = LOGS / f"atualizacao_{dt.date.today():%Y-%m-%d}.log"
    with open(arq, "a", encoding="utf-8") as f:
        # evita duas atualizações ao mesmo tempo (ex.: agendador disparado de novo)
        if LOCK.exists() and (time.time() - LOCK.stat().st_mtime) < LOCK_MAX_H * 3600:
            log(f, "Já existe uma atualização em andamento (lock recente). Nada a fazer.")
            return 0
        LOCK.write_text(f"{os.getpid()} {dt.datetime.now().isoformat()}", encoding="utf-8")
        inicio = time.time()
        log(f, "=== Início da atualização diária ===")
        try:
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            r = subprocess.run([sys.executable, str(AQUI / "painel.py")], cwd=AQUI, env=env, stdout=f, stderr=subprocess.STDOUT,
                               timeout=TIMEOUT_H * 3600)
            ok = r.returncode == 0 and (AQUI / "painel_cvm.html").exists()
            fim = f"{'OK' if ok else 'FALHOU (código ' + str(r.returncode) + ')'} em {(time.time() - inicio) / 60:.1f} min"
        except subprocess.TimeoutExpired:
            ok, fim = False, f"FALHOU: passou de {TIMEOUT_H}h e foi interrompida"
        except Exception as e:  # noqa
            ok, fim = False, f"FALHOU: {e}"
        finally:
            try:
                LOCK.unlink()
            except OSError:
                pass
        log(f, f"=== Fim: {fim} ===")
        (LOGS / "ultima_atualizacao.txt").write_text(f"{dt.datetime.now():%d/%m/%Y %H:%M} - {fim}\n", encoding="utf-8")
        # limpa logs antigos
        corte = time.time() - GUARDAR_LOGS_DIAS * 86400
        for p in LOGS.glob("atualizacao_*.log"):
            if p.stat().st_mtime < corte:
                p.unlink()
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
