@echo off
rem Atualizacao diaria sem interacao (use no Agendador de Tarefas). Log em logs\
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel%==0 (
  python atualizar_diario.py
) else (
  py -3 atualizar_diario.py
)
exit /b %errorlevel%
