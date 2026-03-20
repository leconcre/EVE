# voice/config.py - CONFIGURAÇÕES DO MÓDULO DE VOZ
"""
Configurações centralizadas para o sistema de voz da EVE.
Separa todas as configurações para facilitar ajustes e manutenção.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env se existir
load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# DIRETÓRIOS
# ═══════════════════════════════════════════════════════════════════

# Diretório base do módulo de voz
VOICE_DIR = Path(__file__).parent
ROOT_DIR = VOICE_DIR.parent

# Diretório para modelos baixados
MODELS_DIR = VOICE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Diretório para cache de áudio temporário
CACHE_DIR = VOICE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE ÁUDIO
# ═══════════════════════════════════════════════════════════════════

# Taxa de amostragem padrão (16kHz - ideal para reconhecimento de voz)
SAMPLE_RATE = 16000

# Tamanho do chunk de áudio em frames
CHUNK_SIZE = 1024

# Número de canais (1 = mono, 2 = estéreo)
CHANNELS = 1

# Formato de áudio (16-bit)
AUDIO_FORMAT = "int16"

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE VAD (Voice Activity Detection)
# ═══════════════════════════════════════════════════════════════════

# Agressividade do VAD (0-3, sendo 3 mais agressivo)
# 0 = muito sensível (detecta tudo, incluindo ruídos leves)
# 3 = muito rigoroso (só detecta voz clara)
# Recomendado: 2 para ambientes silenciosos, 3 para ambientes ruidosos
VAD_AGGRESSIVENESS = 2

# Tamanho da janela de VAD em milissegundos (10, 20 ou 30)
VAD_FRAME_DURATION_MS = 30

# Duração mínima de voz para iniciar gravação (segundos)
MIN_SPEECH_DURATION = 0.5

# Duração de silêncio para finalizar gravação (segundos)
SILENCE_DURATION = 1.5

# Threshold de confiança do Silero VAD (0.0-1.0)
# Quanto maior, mais rigoroso (menos falsos positivos)
SILERO_THRESHOLD = 0.5

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE SPEECH-TO-TEXT (Whisper)
# ═══════════════════════════════════════════════════════════════════

# Modelo do Whisper a ser usado
# Opções: tiny, base, small, medium, large-v2, large-v3
# tiny    = ~39M params  - muito rápido, menos preciso
# base    = ~74M params  - rápido, boa precisão
# small   = ~244M params - balanceado (RECOMENDADO)
# medium  = ~769M params - lento, excelente precisão
# large-v3 = ~1550M params - muito lento, melhor precisão
WHISPER_MODEL = "small"

# Idioma padrão (pt para português)
WHISPER_LANGUAGE = "pt"

# Device para inferência ("cpu", "cuda", ou "auto")
# "auto" detecta automaticamente se há GPU disponível
WHISPER_DEVICE = "auto"

# Tipo de computação ("float32", "float16", "int8")
# float16 é mais rápido em GPUs modernas
# int8 é ainda mais rápido, mas pode perder um pouco de qualidade
WHISPER_COMPUTE_TYPE = "float16"

# Beam size para busca (quanto maior, mais preciso mas mais lento)
# Valores típicos: 1-5 (1 = greedy, mais rápido)
WHISPER_BEAM_SIZE = 1

# Usar detecção de idioma automática (desabilitar para performance)
WHISPER_AUTO_DETECT_LANGUAGE = False

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE TEXT-TO-SPEECH (Piper)
# ═══════════════════════════════════════════════════════════════════

# Modelo de voz do Piper (será baixado automaticamente se necessário)
# Português BR: pt_BR-faber-medium (voz masculina, boa qualidade)
# Outros modelos disponíveis em: https://github.com/rhasspy/piper/blob/master/VOICES.md
PIPER_VOICE_MODEL = "pt_BR-faber-medium"

# URL para baixar o modelo (caso não esteja instalado)
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"

# Taxa de fala (0.5 = metade da velocidade, 2.0 = dobro da velocidade)
PIPER_SPEECH_RATE = 1.0

# Volume de saída (0.0-1.0)
PIPER_VOLUME = 1.0

# Qualidade de síntese (quanto maior, melhor qualidade mas mais lento)
PIPER_QUALITY = "medium"

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DO DISCORD
# ═══════════════════════════════════════════════════════════════════

# Token do bot Discord (carregar de variável de ambiente por segurança)
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# Prefixo de comandos do bot
DISCORD_COMMAND_PREFIX = "!"

# Timeout de inatividade em canal de voz (minutos)
# Bot sai do canal após X minutos sem uso
DISCORD_VOICE_TIMEOUT = 10

# Bitrate do áudio do Discord (em kbps)
DISCORD_BITRATE = 96000

# Codec de áudio ("opus" recomendado)
DISCORD_CODEC = "opus"

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE LOGGING
# ═══════════════════════════════════════════════════════════════════

# Nível de log ("DEBUG", "INFO", "WARNING", "ERROR")
LOG_LEVEL = "INFO"

# Salvar logs em arquivo?
SAVE_LOGS = True

# Caminho do arquivo de log
LOG_FILE = VOICE_DIR / "voice.log"

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES AVANÇADAS
# ═══════════════════════════════════════════════════════════════════

# Máximo de tentativas para reconhecimento de voz
MAX_RECOGNITION_RETRIES = 3

# Timeout para reconhecimento (segundos)
RECOGNITION_TIMEOUT = 30

# Usar processamento de áudio melhorado (redução de ruído, etc.)
USE_AUDIO_ENHANCEMENT = True

# Habilitar cache de transcrições
ENABLE_TRANSCRIPTION_CACHE = True

# Duração máxima de gravação permitida (segundos)
MAX_RECORDING_DURATION = 60

# Usar GPU se disponível (para Whisper)
USE_GPU_IF_AVAILABLE = True

# ═══════════════════════════════════════════════════════════════════
# VALIDAÇÃO DE CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════

def validate_config():
    """
    Valida as configurações e retorna avisos se algo estiver incorreto.
    """
    warnings = []

    # Verifica token do Discord
    if not DISCORD_TOKEN:
        warnings.append("⚠️ DISCORD_BOT_TOKEN não configurado. Defina a variável de ambiente.")

    # Verifica modelo Whisper
    valid_whisper_models = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
    if WHISPER_MODEL not in valid_whisper_models:
        warnings.append(f"⚠️ Modelo Whisper inválido: {WHISPER_MODEL}")

    # Verifica VAD
    if not (0 <= VAD_AGGRESSIVENESS <= 3):
        warnings.append("⚠️ VAD_AGGRESSIVENESS deve estar entre 0 e 3")

    # Verifica frame duration
    if VAD_FRAME_DURATION_MS not in [10, 20, 30]:
        warnings.append("⚠️ VAD_FRAME_DURATION_MS deve ser 10, 20 ou 30")

    return warnings


# ═══════════════════════════════════════════════════════════════════
# PERFIS DE CONFIGURAÇÃO PREDEFINIDOS
# ═══════════════════════════════════════════════════════════════════

# Perfil para máxima velocidade (sacrifica qualidade)
PROFILE_SPEED = {
    "WHISPER_MODEL": "tiny",
    "WHISPER_BEAM_SIZE": 1,
    "WHISPER_COMPUTE_TYPE": "int8",
    "PIPER_QUALITY": "low",
    "USE_AUDIO_ENHANCEMENT": False,
}

# Perfil para máxima qualidade (sacrifica velocidade)
PROFILE_QUALITY = {
    "WHISPER_MODEL": "medium",
    "WHISPER_BEAM_SIZE": 5,
    "WHISPER_COMPUTE_TYPE": "float32",
    "PIPER_QUALITY": "high",
    "USE_AUDIO_ENHANCEMENT": True,
}

# Perfil balanceado (padrão recomendado)
PROFILE_BALANCED = {
    "WHISPER_MODEL": "small",
    "WHISPER_BEAM_SIZE": 1,
    "WHISPER_COMPUTE_TYPE": "float16",
    "PIPER_QUALITY": "medium",
    "USE_AUDIO_ENHANCEMENT": True,
}


def apply_profile(profile_name: str):
    """
    Aplica um perfil de configuração predefinido.

    Args:
        profile_name: "speed", "quality" ou "balanced"
    """
    profiles = {
        "speed": PROFILE_SPEED,
        "quality": PROFILE_QUALITY,
        "balanced": PROFILE_BALANCED,
    }

    if profile_name not in profiles:
        raise ValueError(f"Perfil desconhecido: {profile_name}. Use: speed, quality ou balanced")

    profile = profiles[profile_name]
    globals().update(profile)
    print(f"✅ Perfil '{profile_name}' aplicado com sucesso!")


# Executa validação ao importar
if __name__ != "__main__":
    _warnings = validate_config()
    if _warnings:
        for w in _warnings:
            try:
                print(w)
            except UnicodeEncodeError:
                # Fallback para consoles que nao suportam Unicode
                print(w.encode('ascii', 'replace').decode('ascii'))
