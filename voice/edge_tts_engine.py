# voice/edge_tts_engine.py - ENGINE EDGE TTS (MICROSOFT)
"""
Engine de TTS usando Microsoft Edge TTS (vozes neurais).

Vantagens:
- Qualidade excelente (vozes neurais)
- Fácil de instalar
- Gratuito
- Várias vozes em português
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional
import numpy as np

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ edge-tts não disponível - instale com: pip install edge-tts")

from . import config
from .audio_utils import load_audio

logger = logging.getLogger("eve.voice.edge_tts")


# ═══════════════════════════════════════════════════════════════════
# VOZES DISPONÍVEIS EM PT-BR
# ═══════════════════════════════════════════════════════════════════

BRAZILIAN_VOICES = {
    # Femininas
    "francisca": "pt-BR-FranciscaNeural",  # Jovem, clara
    "brenda": "pt-BR-BrendaNeural",
    "elza": "pt-BR-ElzaNeural",
    "leila": "pt-BR-LeilaNeural",
    "leticia": "pt-BR-LeticiaNeural",
    "yara": "pt-BR-YaraNeural",  # Recomendada para EVE

    # Masculinas
    "antonio": "pt-BR-AntonioNeural",
    "donato": "pt-BR-DonatoNeural",  # Mais velho
    "fabio": "pt-BR-FabioNeural",
    "humberto": "pt-BR-HumbertoNeural",  # Sênior
    "julio": "pt-BR-JulioNeural",
    "nicolau": "pt-BR-NicolauNeural",
    "valerio": "pt-BR-ValerioNeural",

    # Infantis
    "giovanna": "pt-BR-GiovannaNeural",
    "manuela": "pt-BR-ManuelaNeural",
}

# Voz padrão da EVE: Francisca (clara, jovem, amigável)
DEFAULT_VOICE = "pt-BR-FranciscaNeural"


# ═══════════════════════════════════════════════════════════════════
# ENGINE EDGE TTS
# ═══════════════════════════════════════════════════════════════════

class EdgeTTSEngine:
    """
    Engine de TTS usando Microsoft Edge (vozes neurais).
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ):
        """
        Inicializa Edge TTS Engine.

        Args:
            voice: Nome da voz (use BRAZILIAN_VOICES ou nome completo)
            rate: Taxa de fala (+50% = mais rápido, -50% = mais lento)
            volume: Volume (+50% = mais alto, -50% = mais baixo)
            pitch: Pitch da voz (+10Hz = mais agudo, -10Hz = mais grave)
        """
        if not EDGE_TTS_AVAILABLE:
            raise RuntimeError("edge-tts não instalado. Instale com: pip install edge-tts")

        # Converte nome curto para nome completo
        if voice in BRAZILIAN_VOICES:
            self.voice = BRAZILIAN_VOICES[voice]
        else:
            self.voice = voice

        self.rate = rate
        self.volume = volume
        self.pitch = pitch

        logger.info(f"✅ Edge TTS inicializado com voz: {self.voice}")

    async def synthesize_async(
        self,
        text: str,
        output_file: Optional[Path] = None
    ) -> Path:
        """
        Sintetiza texto em áudio (async).

        Args:
            text: Texto para sintetizar
            output_file: Caminho do arquivo de saída (opcional)

        Returns:
            Path do arquivo de áudio gerado
        """
        if output_file is None:
            output_file = config.CACHE_DIR / "edge_tts_output.mp3"

        try:
            # Cria comunicador Edge TTS
            communicate = edge_tts.Communicate(
                text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch
            )

            # Salva áudio
            await communicate.save(str(output_file))
            logger.info(f"✅ Áudio sintetizado: {output_file}")

            return output_file

        except Exception as e:
            logger.error(f"Erro ao sintetizar com Edge TTS: {e}")
            raise

    def synthesize(
        self,
        text: str,
        output_file: Optional[Path] = None
    ) -> Path:
        """
        Sintetiza texto em áudio (versão síncrona).

        Args:
            text: Texto para sintetizar
            output_file: Caminho do arquivo de saída

        Returns:
            Path do arquivo de áudio gerado
        """
        # Executa versão async em loop síncrono
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.synthesize_async(text, output_file)
        )

    def synthesize_to_numpy(self, text: str) -> np.ndarray:
        """
        Sintetiza texto e retorna como array NumPy.

        Args:
            text: Texto para sintetizar

        Returns:
            Array NumPy com áudio
        """
        # Sintetiza para arquivo temporário
        temp_file = self.synthesize(text)

        # Converte MP3 para WAV e carrega
        wav_file = config.CACHE_DIR / "edge_tts_output.wav"

        # Usa ffmpeg para converter MP3 -> WAV
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(temp_file),
                "-ar", str(config.SAMPLE_RATE),
                "-ac", "1",
                str(wav_file)
            ], check=True, capture_output=True)

            # Carrega WAV
            audio, sr = load_audio(wav_file, target_sr=config.SAMPLE_RATE)
            return audio

        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao converter MP3 para WAV: {e}")
            raise
        except FileNotFoundError:
            logger.error("FFmpeg não encontrado. Instale: winget install FFmpeg")
            raise

    def list_voices(self) -> list:
        """Lista todas as vozes disponíveis em português."""
        return list(BRAZILIAN_VOICES.keys())

    def get_voice_info(self) -> dict:
        """Retorna informações sobre a voz atual."""
        return {
            "voice": self.voice,
            "rate": self.rate,
            "volume": self.volume,
            "pitch": self.pitch,
            "available_voices": self.list_voices()
        }


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

def speak_edge(
    text: str,
    voice: str = "francisca",
    rate: str = "+0%",
    play: bool = True
):
    """
    Fala usando Edge TTS (função de conveniência).

    Args:
        text: Texto para falar
        voice: Nome da voz (veja BRAZILIAN_VOICES)
        rate: Taxa de fala
        play: Se deve reproduzir
    """
    engine = EdgeTTSEngine(voice=voice, rate=rate)
    audio_file = engine.synthesize(text)

    if play:
        try:
            import sounddevice as sd
            audio = engine.synthesize_to_numpy(text)
            sd.play(audio, samplerate=config.SAMPLE_RATE)
            sd.wait()
        except ImportError:
            logger.warning("sounddevice não disponível - áudio salvo mas não reproduzido")
            logger.info(f"Áudio salvo em: {audio_file}")


def list_brazilian_voices():
    """Lista todas as vozes brasileiras disponíveis."""
    print("🇧🇷 Vozes em Português Brasileiro:")
    print()
    print("Femininas:")
    for name, full_name in BRAZILIAN_VOICES.items():
        if any(x in full_name for x in ["Francisca", "Brenda", "Elza", "Leila", "Leticia", "Yara"]):
            print(f"  - {name:12} ({full_name})")

    print("\nMasculinas:")
    for name, full_name in BRAZILIAN_VOICES.items():
        if any(x in full_name for x in ["Antonio", "Donato", "Fabio", "Humberto", "Julio", "Nicolau", "Valerio"]):
            print(f"  - {name:12} ({full_name})")

    print("\nInfantis:")
    for name, full_name in BRAZILIAN_VOICES.items():
        if any(x in full_name for x in ["Giovanna", "Manuela"]):
            print(f"  - {name:12} ({full_name})")


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testando Edge TTS...")

    # Lista vozes
    list_brazilian_voices()

    # Testa síntese
    print("\n🔊 Testando síntese...")
    engine = EdgeTTSEngine(voice="francisca")

    text = "Olá! Eu sou a EVE, sua assistente com voz da Microsoft Edge TTS."
    print(f"Texto: {text}")

    audio_file = engine.synthesize(text)
    print(f"✅ Áudio gerado: {audio_file}")

    # Teste de reprodução
    try:
        speak_edge(text, voice="yara")
        print("✅ Teste concluído!")
    except Exception as e:
        print(f"⚠️ Erro ao reproduzir: {e}")
