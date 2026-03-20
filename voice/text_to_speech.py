# voice/text_to_speech.py - SÍNTESE DE VOZ (TTS)
"""
Sistema de Text-to-Speech com suporte a múltiplas engines.

Funcionalidades:
- Síntese de voz usando Piper (principal)
- Suporte para outras engines (Coqui TTS, gTTS, pyttsx3)
- Sistema modular para fácil troca de voz
- Controle de velocidade, volume e pitch
- Salvamento e reprodução de áudio
"""

import numpy as np
import logging
import subprocess
import io
import wave
from typing import Optional, Union
from pathlib import Path

# Tenta importar engines de TTS
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("⚠️ pyttsx3 não disponível")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️ gTTS não disponível")

try:
    from TTS.api import TTS as CoquiTTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    print("⚠️ Coqui TTS não disponível")

try:
    from .edge_tts_engine import EdgeTTSEngine, EDGE_TTS_AVAILABLE
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ Edge TTS não disponível")

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("⚠️ sounddevice não disponível - reprodução de áudio desabilitada")

from . import config
from .audio_utils import save_audio, load_audio

logger = logging.getLogger("eve.voice.tts")


# ═══════════════════════════════════════════════════════════════════
# CLASSE BASE DE TTS
# ═══════════════════════════════════════════════════════════════════

class TextToSpeech:
    """
    Sistema de síntese de voz modular.

    Suporta múltiplas engines:
    1. Edge TTS (recomendado - online, excelente qualidade)
    2. Piper (offline, alta qualidade)
    3. Coqui TTS (offline, muito boa qualidade)
    4. gTTS (online, Google TTS)
    5. pyttsx3 (offline, qualidade básica)
    """

    def __init__(
        self,
        engine: str = "piper",
        voice_model: Optional[str] = None,
        language: str = "pt-BR",
        rate: float = config.PIPER_SPEECH_RATE,
        volume: float = config.PIPER_VOLUME
    ):
        """
        Inicializa o sistema de TTS.

        Args:
            engine: Engine a usar ("piper", "coqui", "gtts", "pyttsx3")
            voice_model: Modelo de voz específico (depende da engine)
            language: Código do idioma
            rate: Taxa de fala (0.5 = metade, 2.0 = dobro)
            volume: Volume (0.0-1.0)
        """
        self.engine_name = engine.lower()
        self.voice_model = voice_model
        self.language = language
        self.rate = rate
        self.volume = volume

        # Inicializa engine
        self.engine = None
        self._initialize_engine()

        logger.info(f"✅ TTS inicializado com engine: {self.engine_name}")

    def _initialize_engine(self):
        """Inicializa a engine de TTS escolhida."""
        if self.engine_name == "edge":
            self._init_edge()
        elif self.engine_name == "piper":
            self._init_piper()
        elif self.engine_name == "coqui":
            self._init_coqui()
        elif self.engine_name == "gtts":
            self._init_gtts()
        elif self.engine_name == "pyttsx3":
            self._init_pyttsx3()
        else:
            raise ValueError(
                f"Engine desconhecida: {self.engine_name}\n"
                f"Use: edge, piper, coqui, gtts ou pyttsx3"
            )

    def _init_piper(self):
        """Inicializa Piper TTS."""
        logger.info("Verificando Piper TTS...")

        # Verifica se piper está instalado
        try:
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("✅ Piper encontrado")
                self.engine = "piper_binary"
            else:
                raise FileNotFoundError()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("⚠️ Piper não encontrado no PATH")
            logger.info("Tentando usar piper-tts Python...")

            try:
                # Tenta importar piper-tts como biblioteca Python
                import piper
                self.engine = "piper_python"
                logger.info("✅ piper-tts (Python) carregado")
            except ImportError:
                logger.error(
                    "❌ Piper não disponível. Instale com:\n"
                    "  Windows: winget install rhasspy.piper\n"
                    "  ou: pip install piper-tts"
                )
                raise RuntimeError("Piper não está instalado")

        # Verifica/baixa modelo de voz
        self._setup_piper_model()

    def _setup_piper_model(self):
        """Configura o modelo de voz do Piper."""
        model_name = self.voice_model or config.PIPER_VOICE_MODEL
        model_file = config.MODELS_DIR / f"{model_name}.onnx"
        config_file = config.MODELS_DIR / f"{model_name}.onnx.json"

        # Baixa modelo se não existir
        if not model_file.exists() or not config_file.exists():
            logger.info(f"Baixando modelo de voz: {model_name}...")
            self._download_piper_model(model_name, model_file, config_file)

        self.piper_model_path = model_file
        logger.info(f"Modelo Piper: {model_file}")

    def _download_piper_model(self, model_name: str, model_file: Path, config_file: Path):
        """
        Baixa modelo do Piper.

        Args:
            model_name: Nome do modelo
            model_file: Caminho do arquivo .onnx
            config_file: Caminho do arquivo .json
        """
        import urllib.request

        try:
            # URLs dos modelos
            base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
            model_url = f"{base_url}/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
            config_url = f"{base_url}/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"

            # Baixa modelo
            logger.info("Baixando arquivo .onnx...")
            urllib.request.urlretrieve(model_url, model_file)

            # Baixa config
            logger.info("Baixando arquivo .json...")
            urllib.request.urlretrieve(config_url, config_file)

            logger.info("✅ Modelo baixado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao baixar modelo: {e}")
            raise

    def _init_coqui(self):
        """Inicializa Coqui TTS."""
        if not COQUI_AVAILABLE:
            raise RuntimeError("Coqui TTS não está instalado. Instale com: pip install TTS")

        logger.info("Carregando Coqui TTS...")
        try:
            # Usa modelo multilíngue ou específico de português
            model_name = self.voice_model or "tts_models/pt/cv/vits"
            self.engine = CoquiTTS(model_name=model_name)
            logger.info("✅ Coqui TTS carregado")
        except Exception as e:
            logger.error(f"Erro ao carregar Coqui TTS: {e}")
            raise

    def _init_gtts(self):
        """Inicializa gTTS (Google TTS)."""
        if not GTTS_AVAILABLE:
            raise RuntimeError("gTTS não está instalado. Instale com: pip install gtts")

        logger.info("✅ gTTS inicializado (online)")
        self.engine = "gtts"

    def _init_pyttsx3(self):
        """Inicializa pyttsx3."""
        if not PYTTSX3_AVAILABLE:
            raise RuntimeError("pyttsx3 não está instalado. Instale com: pip install pyttsx3")

        logger.info("Inicializando pyttsx3...")
        try:
            self.engine = pyttsx3.init()

            # Configura voz em português (se disponível)
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if 'portuguese' in voice.name.lower() or 'brazil' in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    break

            # Configura taxa e volume
            self.engine.setProperty('rate', int(200 * self.rate))
            self.engine.setProperty('volume', self.volume)

            logger.info("✅ pyttsx3 inicializado")
        except Exception as e:
            logger.error(f"Erro ao inicializar pyttsx3: {e}")
            raise

    def _init_edge(self):
        """Inicializa Edge TTS (Microsoft)."""
        if not EDGE_TTS_AVAILABLE:
            raise RuntimeError("edge-tts não está instalado. Instale com: pip install edge-tts")

        logger.info("Inicializando Edge TTS...")
        try:
            # Converte rate de 0.5-2.0 para porcentagem Edge TTS
            # rate 1.0 = +0%, rate 1.5 = +50%, rate 0.5 = -50%
            rate_percent = int((self.rate - 1.0) * 100)
            rate_str = f"{rate_percent:+d}%"

            # Voice model pode ser nome curto ou completo
            voice = self.voice_model or "francisca"  # Voz padrão para EVE

            self.engine = EdgeTTSEngine(
                voice=voice,
                rate=rate_str,
                volume=f"{int((self.volume - 1.0) * 100):+d}%"
            )
            logger.info("✅ Edge TTS inicializado")
        except Exception as e:
            logger.error(f"Erro ao inicializar Edge TTS: {e}")
            raise

    def synthesize(
        self,
        text: str,
        save_to: Optional[Path] = None,
        play: bool = False
    ) -> Optional[np.ndarray]:
        """
        Sintetiza texto em áudio.

        Args:
            text: Texto para falar
            save_to: Caminho para salvar áudio (opcional)
            play: Se deve reproduzir o áudio

        Returns:
            Array NumPy com áudio ou None
        """
        if not text or len(text.strip()) == 0:
            logger.warning("Texto vazio fornecido para síntese")
            return None

        logger.info(f"🔊 Sintetizando: {text[:50]}...")

        try:
            if self.engine_name == "edge":
                audio = self._synthesize_edge(text)
            elif self.engine_name == "piper":
                audio = self._synthesize_piper(text)
            elif self.engine_name == "coqui":
                audio = self._synthesize_coqui(text)
            elif self.engine_name == "gtts":
                audio = self._synthesize_gtts(text)
            elif self.engine_name == "pyttsx3":
                audio = self._synthesize_pyttsx3(text)
            else:
                raise ValueError(f"Engine não suportada: {self.engine_name}")

            # Salva se solicitado
            if save_to and audio is not None:
                save_audio(audio, save_to, config.SAMPLE_RATE)

            # Reproduz se solicitado
            if play and audio is not None:
                self.play_audio(audio)

            logger.info("✅ Síntese concluída")
            return audio

        except Exception as e:
            logger.error(f"Erro na síntese: {e}")
            return None

    def _synthesize_piper(self, text: str) -> np.ndarray:
        """Sintetiza usando Piper."""
        # Cria arquivo temporário para output
        output_file = config.CACHE_DIR / "temp_piper_output.wav"

        try:
            # Executa Piper via linha de comando
            cmd = [
                "piper",
                "--model", str(self.piper_model_path),
                "--output_file", str(output_file)
            ]

            # Ajusta taxa de fala se diferente de 1.0
            if self.rate != 1.0:
                cmd.extend(["--length_scale", str(1.0 / self.rate)])

            # Executa
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input=text, timeout=30)

            if process.returncode != 0:
                raise RuntimeError(f"Piper falhou: {stderr}")

            # Carrega áudio gerado
            audio, sr = load_audio(output_file, target_sr=config.SAMPLE_RATE)

            # Ajusta volume
            if self.volume != 1.0:
                audio = audio * self.volume

            return audio

        except subprocess.TimeoutExpired:
            logger.error("Timeout ao executar Piper")
            raise
        except Exception as e:
            logger.error(f"Erro no Piper: {e}")
            raise

    def _synthesize_coqui(self, text: str) -> np.ndarray:
        """Sintetiza usando Coqui TTS."""
        try:
            # Gera áudio
            wav = self.engine.tts(text=text)

            # Converte para NumPy array
            audio = np.array(wav, dtype=np.float32)

            # Ajusta taxa e volume (simplificado)
            if self.volume != 1.0:
                audio = audio * self.volume

            return audio

        except Exception as e:
            logger.error(f"Erro no Coqui TTS: {e}")
            raise

    def _synthesize_gtts(self, text: str) -> np.ndarray:
        """Sintetiza usando gTTS (Google TTS)."""
        try:
            # Gera TTS
            tts = gTTS(text=text, lang='pt', slow=False)

            # Salva em buffer
            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)

            # Salva temporariamente como arquivo para carregar
            temp_file = config.CACHE_DIR / "temp_gtts.mp3"
            with open(temp_file, 'wb') as f:
                f.write(buffer.read())

            # Converte MP3 para WAV (requer ffmpeg ou pydub)
            # Por simplicidade, apenas retorna None e avisa
            logger.warning("gTTS retorna MP3 - conversão para WAV não implementada")
            logger.info(f"Áudio salvo em: {temp_file}")

            return None  # TODO: Implementar conversão MP3 -> WAV

        except Exception as e:
            logger.error(f"Erro no gTTS: {e}")
            raise

    def _synthesize_pyttsx3(self, text: str) -> np.ndarray:
        """Sintetiza usando pyttsx3."""
        try:
            # pyttsx3 salva diretamente em arquivo
            output_file = config.CACHE_DIR / "temp_pyttsx3.wav"
            self.engine.save_to_file(text, str(output_file))
            self.engine.runAndWait()

            # Carrega áudio gerado
            audio, sr = load_audio(output_file, target_sr=config.SAMPLE_RATE)
            return audio

        except Exception as e:
            logger.error(f"Erro no pyttsx3: {e}")
            raise

    def _synthesize_edge(self, text: str) -> np.ndarray:
        """Sintetiza usando Edge TTS (Microsoft)."""
        try:
            # Usa EdgeTTSEngine para sintetizar
            audio = self.engine.synthesize_to_numpy(text)
            return audio

        except Exception as e:
            logger.error(f"Erro no Edge TTS: {e}")
            raise

    def play_audio(self, audio: np.ndarray, sample_rate: int = config.SAMPLE_RATE):
        """
        Reproduz áudio.

        Args:
            audio: Array NumPy com áudio
            sample_rate: Taxa de amostragem
        """
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning("sounddevice não disponível - não é possível reproduzir")
            return

        try:
            logger.info("🔊 Reproduzindo áudio...")
            sd.play(audio, samplerate=sample_rate)
            sd.wait()  # Aguarda terminar
        except Exception as e:
            logger.error(f"Erro ao reproduzir áudio: {e}")

    def get_engine_info(self) -> dict:
        """Retorna informações sobre a engine."""
        return {
            "engine": self.engine_name,
            "voice_model": self.voice_model,
            "language": self.language,
            "rate": self.rate,
            "volume": self.volume
        }


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

# Instância global (lazy loading)
_tts_instance: Optional[TextToSpeech] = None


def get_tts(engine: str = "piper") -> TextToSpeech:
    """
    Retorna instância global do TTS (singleton).

    Args:
        engine: Nome da engine

    Returns:
        Instância de TextToSpeech
    """
    global _tts_instance
    if _tts_instance is None or _tts_instance.engine_name != engine:
        _tts_instance = TextToSpeech(engine=engine)
    return _tts_instance


def speak(text: str, engine: str = "piper", play: bool = True, save_to: Optional[Path] = None):
    """
    Fala um texto (função de conveniência).

    Args:
        text: Texto para falar
        engine: Engine a usar
        play: Se deve reproduzir
        save_to: Caminho para salvar
    """
    tts = get_tts(engine)
    tts.synthesize(text, save_to=save_to, play=play)


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Teste básico
    print("Testando Text-to-Speech...")

    # Testa com pyttsx3 (mais fácil de instalar)
    if PYTTSX3_AVAILABLE:
        print("\nTestando pyttsx3...")
        tts = TextToSpeech(engine="pyttsx3")
        print(f"Engine: {tts.get_engine_info()}")
        tts.synthesize("Olá, eu sou a EVE!", play=True)

    print("\n✅ Testes concluídos!")
