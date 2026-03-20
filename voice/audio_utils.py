# voice/audio_utils.py - UTILITÁRIOS DE ÁUDIO E VAD
"""
Utilitários para processamento de áudio e detecção de atividade de voz (VAD).

Funcionalidades:
- Voice Activity Detection (VAD) usando Silero VAD
- Processamento e normalização de áudio
- Redução de ruído
- Conversão de formatos
- Salvamento e carregamento de áudio
"""

import numpy as np
import io
import logging
import wave
from typing import Optional, Tuple, List
from pathlib import Path

# Tenta importar bibliotecas opcionais
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch não disponível - VAD Silero desabilitado")

try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    print("⚠️ webrtcvad não disponível - usando fallback")

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    print("⚠️ noisereduce não disponível - redução de ruído desabilitada")

from . import config

logger = logging.getLogger("eve.voice.audio")

# ═══════════════════════════════════════════════════════════════════
# CLASSE DE VAD (Voice Activity Detection)
# ═══════════════════════════════════════════════════════════════════

class VoiceActivityDetector:
    """
    Detecta quando há voz no áudio usando múltiplas estratégias.

    Suporta:
    1. Silero VAD (deep learning - mais preciso)
    2. WebRTC VAD (rápido e leve)
    3. Energy-based VAD (fallback simples)
    """

    def __init__(
        self,
        sample_rate: int = config.SAMPLE_RATE,
        use_silero: bool = True,
        threshold: float = config.SILERO_THRESHOLD
    ):
        """
        Inicializa o detector de voz.

        Args:
            sample_rate: Taxa de amostragem do áudio (Hz)
            use_silero: Se deve usar Silero VAD (requer PyTorch)
            threshold: Threshold de confiança (0.0-1.0)
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.model = None
        self.webrtc_vad = None

        # Tenta carregar Silero VAD
        if use_silero and TORCH_AVAILABLE:
            try:
                logger.info("Carregando Silero VAD...")
                self.model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                self.model.eval()
                logger.info("✅ Silero VAD carregado com sucesso")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao carregar Silero VAD: {e}")
                self.model = None

        # Fallback para WebRTC VAD
        if self.model is None and WEBRTC_AVAILABLE:
            try:
                logger.info("Usando WebRTC VAD como alternativa...")
                self.webrtc_vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
                logger.info("✅ WebRTC VAD inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao inicializar WebRTC VAD: {e}")

        # Fallback final: Energy-based VAD
        if self.model is None and self.webrtc_vad is None:
            logger.warning("⚠️ Usando VAD baseado em energia (menos preciso)")

    def detect_speech_silero(self, audio_chunk: np.ndarray) -> float:
        """
        Detecta voz usando Silero VAD (deep learning).

        Args:
            audio_chunk: Array NumPy com áudio (float32, -1 a 1)

        Returns:
            Probabilidade de voz (0.0-1.0)
        """
        if self.model is None:
            return 0.0

        try:
            # Converte para tensor do PyTorch
            audio_tensor = torch.from_numpy(audio_chunk).float()

            # Garante que tem sample rate correto
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, self.sample_rate).item()

            return speech_prob
        except Exception as e:
            logger.error(f"Erro no Silero VAD: {e}")
            return 0.0

    def detect_speech_webrtc(self, audio_chunk: bytes) -> bool:
        """
        Detecta voz usando WebRTC VAD.

        Args:
            audio_chunk: Bytes de áudio (16-bit PCM)

        Returns:
            True se detectou voz, False caso contrário
        """
        if self.webrtc_vad is None:
            return False

        try:
            # WebRTC VAD precisa de chunks de 10, 20 ou 30ms
            # Tamanho do chunk em bytes = sample_rate * (duration_ms / 1000) * 2 (16-bit)
            frame_duration_ms = config.VAD_FRAME_DURATION_MS
            frame_size = int(self.sample_rate * frame_duration_ms / 1000) * 2

            # Se o chunk for maior, processa em frames
            is_speech = False
            for i in range(0, len(audio_chunk), frame_size):
                frame = audio_chunk[i:i + frame_size]
                if len(frame) == frame_size:
                    is_speech = self.webrtc_vad.is_speech(frame, self.sample_rate)
                    if is_speech:
                        break

            return is_speech
        except Exception as e:
            logger.error(f"Erro no WebRTC VAD: {e}")
            return False

    def detect_speech_energy(self, audio_chunk: np.ndarray, threshold: float = 0.01) -> bool:
        """
        Detecta voz baseado em energia do sinal (fallback simples).

        Args:
            audio_chunk: Array NumPy com áudio
            threshold: Threshold de energia

        Returns:
            True se detectou atividade, False caso contrário
        """
        try:
            # Calcula RMS (Root Mean Square) como medida de energia
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            return rms > threshold
        except Exception as e:
            logger.error(f"Erro no VAD de energia: {e}")
            return False

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Detecta se há voz no chunk de áudio usando o melhor método disponível.

        Args:
            audio_chunk: Array NumPy com áudio (float32 ou int16)

        Returns:
            True se há voz, False caso contrário
        """
        # Normaliza para float32 entre -1 e 1
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio_float = audio_chunk.astype(np.float32)

        # 1. Tenta Silero VAD (mais preciso)
        if self.model is not None:
            speech_prob = self.detect_speech_silero(audio_float)
            return speech_prob > self.threshold

        # 2. Fallback para WebRTC VAD
        if self.webrtc_vad is not None:
            audio_bytes = (audio_float * 32768).astype(np.int16).tobytes()
            return self.detect_speech_webrtc(audio_bytes)

        # 3. Fallback para energy-based VAD
        return self.detect_speech_energy(audio_float)


# ═══════════════════════════════════════════════════════════════════
# PROCESSAMENTO DE ÁUDIO
# ═══════════════════════════════════════════════════════════════════

def normalize_audio(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Normaliza o volume do áudio para um nível alvo.

    Args:
        audio: Array NumPy com áudio (float32)
        target_db: Nível alvo em decibéis

    Returns:
        Áudio normalizado
    """
    try:
        # Calcula RMS atual
        rms = np.sqrt(np.mean(audio ** 2))

        # Evita divisão por zero
        if rms < 1e-10:
            return audio

        # Calcula ganho necessário
        target_rms = 10 ** (target_db / 20)
        gain = target_rms / rms

        # Aplica ganho
        normalized = audio * gain

        # Limita para evitar clipping
        normalized = np.clip(normalized, -1.0, 1.0)

        return normalized
    except Exception as e:
        logger.error(f"Erro ao normalizar áudio: {e}")
        return audio


def reduce_noise(audio: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> np.ndarray:
    """
    Reduz ruído de fundo do áudio.

    Args:
        audio: Array NumPy com áudio
        sample_rate: Taxa de amostragem

    Returns:
        Áudio com ruído reduzido
    """
    if not NOISEREDUCE_AVAILABLE or not config.USE_AUDIO_ENHANCEMENT:
        return audio

    try:
        logger.debug("Aplicando redução de ruído...")
        reduced = nr.reduce_noise(y=audio, sr=sample_rate, stationary=True)
        return reduced
    except Exception as e:
        logger.error(f"Erro na redução de ruído: {e}")
        return audio


def trim_silence(
    audio: np.ndarray,
    sample_rate: int = config.SAMPLE_RATE,
    threshold_db: float = -40.0
) -> np.ndarray:
    """
    Remove silêncio do início e fim do áudio.

    Args:
        audio: Array NumPy com áudio
        sample_rate: Taxa de amostragem
        threshold_db: Threshold de silêncio em dB

    Returns:
        Áudio sem silêncio nas pontas
    """
    try:
        # Calcula energia em janelas
        frame_length = int(sample_rate * 0.02)  # 20ms
        energy = np.array([
            np.sum(audio[i:i + frame_length] ** 2)
            for i in range(0, len(audio) - frame_length, frame_length)
        ])

        # Converte para dB
        energy_db = 10 * np.log10(energy + 1e-10)

        # Encontra onde começa e termina a voz
        threshold = np.max(energy_db) + threshold_db
        voice_frames = np.where(energy_db > threshold)[0]

        if len(voice_frames) == 0:
            return audio

        start = voice_frames[0] * frame_length
        end = (voice_frames[-1] + 1) * frame_length

        return audio[start:end]
    except Exception as e:
        logger.error(f"Erro ao remover silêncio: {e}")
        return audio


def resample_audio(
    audio: np.ndarray,
    orig_sr: int,
    target_sr: int = config.SAMPLE_RATE
) -> np.ndarray:
    """
    Reamostra áudio para uma nova taxa de amostragem.

    Args:
        audio: Array NumPy com áudio
        orig_sr: Taxa de amostragem original
        target_sr: Taxa de amostragem alvo

    Returns:
        Áudio reamostrado
    """
    if orig_sr == target_sr:
        return audio

    try:
        # Calcula fator de reamostragem
        ratio = target_sr / orig_sr

        # Reamostra usando interpolação linear
        indices = np.arange(0, len(audio), 1 / ratio)
        resampled = np.interp(indices, np.arange(len(audio)), audio)

        return resampled.astype(audio.dtype)
    except Exception as e:
        logger.error(f"Erro ao reamostrar áudio: {e}")
        return audio


# ═══════════════════════════════════════════════════════════════════
# SALVAMENTO E CARREGAMENTO
# ═══════════════════════════════════════════════════════════════════

def save_audio(
    audio: np.ndarray,
    filepath: Path,
    sample_rate: int = config.SAMPLE_RATE
) -> bool:
    """
    Salva áudio em arquivo WAV.

    Args:
        audio: Array NumPy com áudio (float32 ou int16)
        filepath: Caminho do arquivo de saída
        sample_rate: Taxa de amostragem

    Returns:
        True se salvou com sucesso
    """
    try:
        # Converte para int16 se necessário
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio_int = (audio * 32767).astype(np.int16)
        else:
            audio_int = audio.astype(np.int16)

        # Salva WAV
        with wave.open(str(filepath), 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int.tobytes())

        logger.info(f"✅ Áudio salvo: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar áudio: {e}")
        return False


def load_audio(filepath: Path, target_sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
    """
    Carrega áudio de arquivo WAV.

    Args:
        filepath: Caminho do arquivo
        target_sr: Taxa de amostragem alvo (opcional, reamostra se diferente)

    Returns:
        Tupla (áudio como float32, sample_rate)
    """
    try:
        with wave.open(str(filepath), 'rb') as wf:
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16)

        # Converte para float32
        audio_float = audio.astype(np.float32) / 32768.0

        # Reamostra se necessário
        if target_sr is not None and target_sr != sample_rate:
            audio_float = resample_audio(audio_float, sample_rate, target_sr)
            sample_rate = target_sr

        logger.info(f"✅ Áudio carregado: {filepath}")
        return audio_float, sample_rate
    except Exception as e:
        logger.error(f"Erro ao carregar áudio: {e}")
        return np.array([]), 0


def audio_to_bytes(audio: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> bytes:
    """
    Converte array de áudio para bytes (WAV format).

    Args:
        audio: Array NumPy com áudio
        sample_rate: Taxa de amostragem

    Returns:
        Bytes do áudio em formato WAV
    """
    try:
        # Converte para int16
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio_int = (audio * 32767).astype(np.int16)
        else:
            audio_int = audio.astype(np.int16)

        # Cria WAV em memória
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int.tobytes())

        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Erro ao converter áudio para bytes: {e}")
        return b""


def bytes_to_audio(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """
    Converte bytes (WAV format) para array de áudio.

    Args:
        audio_bytes: Bytes do áudio

    Returns:
        Tupla (áudio como float32, sample_rate)
    """
    try:
        buffer = io.BytesIO(audio_bytes)
        with wave.open(buffer, 'rb') as wf:
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16)

        audio_float = audio.astype(np.float32) / 32768.0
        return audio_float, sample_rate
    except Exception as e:
        logger.error(f"Erro ao converter bytes para áudio: {e}")
        return np.array([]), 0


# ═══════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════

def get_audio_duration(audio: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> float:
    """
    Calcula a duração do áudio em segundos.

    Args:
        audio: Array NumPy com áudio
        sample_rate: Taxa de amostragem

    Returns:
        Duração em segundos
    """
    return len(audio) / sample_rate


def split_audio_chunks(
    audio: np.ndarray,
    chunk_duration: float = 30.0,
    sample_rate: int = config.SAMPLE_RATE
) -> List[np.ndarray]:
    """
    Divide áudio em chunks de duração fixa.

    Args:
        audio: Array NumPy com áudio
        chunk_duration: Duração de cada chunk em segundos
        sample_rate: Taxa de amostragem

    Returns:
        Lista de chunks de áudio
    """
    chunk_size = int(chunk_duration * sample_rate)
    chunks = []

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) > 0:
            chunks.append(chunk)

    return chunks


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Teste do VAD
    print("Testando Voice Activity Detector...")
    vad = VoiceActivityDetector()

    # Cria áudio de teste (1 segundo de silêncio + 1 segundo de "voz" simulada)
    silence = np.zeros(16000, dtype=np.float32)
    noise = np.random.randn(16000).astype(np.float32) * 0.5

    print(f"Silêncio: {vad.is_speech(silence)}")
    print(f"Ruído: {vad.is_speech(noise)}")
    print("✅ Testes concluídos!")
