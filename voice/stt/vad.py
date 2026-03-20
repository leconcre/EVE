"""
voice/stt/vad.py - Voice Activity Detection para Discord

Detecta atividade de voz em streams de áudio.
"""

import numpy as np
from typing import Optional
import logging

logger = logging.getLogger("eve_discord.vad")


class VoiceActivityDetector:
    """
    Detecta atividade de voz usando análise de energia.

    Para Discord, usamos uma abordagem mais simples pois o áudio
    já vem em chunks otimizados.
    """

    def __init__(
        self,
        energy_threshold: float = 0.01,
        silence_duration: float = 1.0,
        sample_rate: int = 48000
    ):
        """
        Inicializa detector de voz.

        Args:
            energy_threshold: Limiar de energia para considerar fala
            silence_duration: Duração de silêncio para finalizar captura (segundos)
            sample_rate: Taxa de amostragem do áudio
        """
        self.energy_threshold = energy_threshold
        self.silence_duration = silence_duration
        self.sample_rate = sample_rate
        self._silence_frames = 0
        self._frames_for_silence = int(silence_duration * sample_rate / 960)  # Discord usa chunks de 960 samples

    def calculate_energy(self, audio_chunk: bytes) -> float:
        """
        Calcula energia de um chunk de áudio.

        Args:
            audio_chunk: Bytes de áudio (PCM 16-bit)

        Returns:
            Energia normalizada (0.0 a 1.0)
        """
        try:
            # Converte bytes para numpy array
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16)

            # Normaliza para -1.0 a 1.0
            audio_float = audio_np.astype(np.float32) / 32768.0

            # Calcula RMS (Root Mean Square)
            rms = np.sqrt(np.mean(audio_float ** 2))

            return float(rms)

        except Exception as e:
            logger.error(f"Erro ao calcular energia: {e}")
            return 0.0

    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Verifica se o chunk contém fala.

        Args:
            audio_chunk: Bytes de áudio

        Returns:
            True se contém fala, False caso contrário
        """
        energy = self.calculate_energy(audio_chunk)
        return energy > self.energy_threshold

    def reset(self):
        """Reseta contador de silêncio."""
        self._silence_frames = 0

    def check_silence(self, audio_chunk: bytes) -> bool:
        """
        Verifica se houve silêncio suficiente para finalizar captura.

        Args:
            audio_chunk: Bytes de áudio

        Returns:
            True se deve finalizar captura, False caso contrário
        """
        if self.is_speech(audio_chunk):
            self._silence_frames = 0
            return False
        else:
            self._silence_frames += 1
            if self._silence_frames >= self._frames_for_silence:
                self.reset()
                return True
        return False


class DiscordVAD:
    """
    VAD otimizado para Discord.

    Discord já faz algum processamento de áudio, então
    usamos uma abordagem mais direta.
    """

    def __init__(self, energy_threshold: float = 0.005):
        """
        Inicializa VAD para Discord.

        Args:
            energy_threshold: Limiar de energia (mais baixo que o padrão)
        """
        self.energy_threshold = energy_threshold

    def is_voice(self, audio_data: bytes) -> bool:
        """
        Verifica se áudio contém voz.

        Args:
            audio_data: Dados de áudio em bytes

        Returns:
            True se contém voz
        """
        if len(audio_data) == 0:
            return False

        try:
            # Converte para numpy
            audio_np = np.frombuffer(audio_data, dtype=np.int16)

            # Normaliza
            audio_float = audio_np.astype(np.float32) / 32768.0

            # Calcula energia RMS
            rms = np.sqrt(np.mean(audio_float ** 2))

            # Verifica se ultrapassa limiar
            return rms > self.energy_threshold

        except Exception as e:
            logger.error(f"Erro no VAD: {e}")
            return False

    def filter_silence(self, audio_data: bytes, min_duration: float = 0.3) -> Optional[bytes]:
        """
        Filtra áudio muito curto (provavelmente ruído).

        Args:
            audio_data: Dados de áudio
            min_duration: Duração mínima em segundos

        Returns:
            Audio data se válido, None se muito curto
        """
        # Estima duração (Discord usa 48kHz, 16-bit, stereo)
        duration = len(audio_data) / (48000 * 2 * 2)  # sample_rate * channels * bytes_per_sample

        if duration < min_duration:
            return None

        return audio_data
