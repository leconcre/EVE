@echo off
REM ================================================================
REM Script de Instalacao - Sistema de Voz EVE com PY-CORD
REM ================================================================

echo.
echo ================================================================
echo    INSTALACAO - SISTEMA DE VOZ EVE
echo ================================================================
echo.
echo Este script vai:
echo   1. Remover discord.py (se instalado)
echo   2. Instalar py-cord com suporte a voz
echo   3. Instalar dependencias (Whisper, VAD, etc)
echo   4. Verificar instalacao
echo.
pause

echo.
echo [1/4] Removendo discord.py...
pip uninstall discord.py discord -y
echo.

echo [2/4] Instalando py-cord...
pip install py-cord[voice] PyNaCl
echo.

echo [3/4] Instalando dependencias STT...
pip install faster-whisper numpy python-dotenv
echo.

echo [4/4] Verificando instalacao...
echo.

python -c "import discord; print('  OK py-cord versao:', discord.__version__)"
if %errorlevel% neq 0 (
    echo   ERRO: py-cord nao instalado!
    pause
    exit /b 1
)

python -c "import discord.sinks; print('  OK discord.sinks disponivel')"
if %errorlevel% neq 0 (
    echo   ERRO: discord.sinks nao disponivel!
    pause
    exit /b 1
)

python -c "from faster_whisper import WhisperModel; print('  OK faster-whisper instalado')"
if %errorlevel% neq 0 (
    echo   AVISO: faster-whisper nao instalado!
)

python -c "import numpy; print('  OK numpy instalado')"
if %errorlevel% neq 0 (
    echo   AVISO: numpy nao instalado!
)

echo.
echo ================================================================
echo    INSTALACAO CONCLUIDA!
echo ================================================================
echo.
echo Proximos passos:
echo   1. Instale FFmpeg: choco install ffmpeg
echo   2. Configure .env com DISCORD_BOT_TOKEN
echo   3. Execute: python eve_discord_bot.py
echo   4. No Discord: !listen
echo.
echo Documentacao: GUIA_PY_CORD.md
echo.
pause
