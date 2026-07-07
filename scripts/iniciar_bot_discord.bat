@echo off
echo ============================================================
echo INICIANDO BOT DISCORD DA EVE
echo ============================================================
echo.

REM Ativa ambiente virtual se existir
if exist .venv\Scripts\activate.bat (
    echo Ativando ambiente virtual...
    call .venv\Scripts\activate.bat
    echo.
)

REM Verifica se .env existe
if not exist .env (
    echo ERRO: Arquivo .env nao encontrado!
    echo.
    echo Crie um arquivo .env com:
    echo DISCORD_BOT_TOKEN=seu_token_aqui
    echo.
    pause
    exit /b 1
)

REM Verifica FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo AVISO: FFmpeg nao encontrado!
    echo Voz no Discord nao funcionara.
    echo.
    echo Instale com: winget install FFmpeg
    echo.
    pause
)

REM Inicia bot
echo Iniciando bot...
echo.
python eve_discord_bot.py

pause
