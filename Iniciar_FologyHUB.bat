@echo off
title FologyHUB Defin - Sistema Pedagógico
cd /d "%~dp0"

:: Verifica se existe ambiente virtual e ativa
if exist .venv\Scripts\activate (
    echo [1/2] Ativando ambiente virtual...
    call .venv\Scripts\activate
) else (
    echo [1/2] Usando Python global...
)

echo [2/2] Iniciando interface...
python launcher.py
pause