@echo off
rem Cria (ou recria) a tarefa diaria no Agendador de Tarefas do Windows, seg a sex as 07:00.
rem Para mudar o horario, edite /ST abaixo (formato HH:MM). Remover: schtasks /Delete /TN "Painel CVM - atualizacao diaria" /F
cd /d "%~dp0"
schtasks /Create /TN "Painel CVM - atualizacao diaria" /TR "\"%~dp0atualizar_diario.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:00 /F
if %errorlevel%==0 (echo Tarefa criada: seg a sex as 07:00.) else (echo Nao foi possivel criar a tarefa - tente executar como administrador, ou configure manualmente no seu agendador.)
pause
