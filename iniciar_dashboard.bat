@echo off
REM Ir para a pasta deste .bat (raiz do projeto, ao lado de config.py e da pasta app\)
cd /d "%~dp0"

REM (Opcional) ativar o ambiente virtual, se usares um:
REM call .venv\Scripts\activate.bat

python iniciar_dashboard.py

REM Mantem a janela aberta para leres o endereco ou um eventual erro
pause