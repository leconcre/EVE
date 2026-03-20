"""
voice/stt/transcriber.py - Transcrição de Áudio usando Faster-Whisper

Converte áudio para texto usando o modelo Whisper.
"""

import numpy as np
from typing import Dict, Optional
from pathlib import Path
import logging
import tempfile
import wave

logger = logging.getLogger("eve_discord.transcriber")

# Importa faster-whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("faster-whisper não instalado! STT não funcionará.")


class AudioTranscriber:
    """
    Transcreve áudio usando Faster-Whisper.

    Otimizado para áudio do Discord (48kHz, stereo).
    """

    def __init__(
        self,
        model_size: str = "small",
        language: str = "pt",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Inicializa transcritor.

        Args:
            model_size: Tamanho do modelo ("tiny", "small", "medium", "large-v3")
            language: Código do idioma ("pt" para português)
            device: "cpu" ou "cuda"
            compute_type: "int8", "int16", "float16", "float32"
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[WhisperModel] = None

        if not WHISPER_AVAILABLE:
            logger.error("faster-whisper não disponível!")
            return

        # Carrega modelo
        self._load_model()

    def _load_model(self):
        """Carrega modelo Whisper."""
        if not WHISPER_AVAILABLE:
            return

        try:
            logger.info(f"Carregando modelo Whisper: {self.model_size}...")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("✅ Modelo Whisper carregado!")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo Whisper: {e}")
            self._model = None

    def convert_discord_audio(self, audio_data: bytes, sample_rate: int = 48000) -> np.ndarray:
        """
        Converte áudio do Discord para formato Whisper.

        Discord usa: 48kHz, 16-bit PCM, stereo
        Whisper espera: 16kHz, float32, mono

        Args:
            audio_data: Bytes de áudio do Discord
            sample_rate: Taxa de amostragem (48000 para Discord)

        Returns:
            Array numpy float32 mono a 16kHz
        """
        try:
            # Converte bytes para int16
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)

            if len(audio_int16) == 0:
                return np.array([], dtype=np.float32)

            # Discord é stereo (2 canais), converte para mono
            if len(audio_int16) % 2 == 0:
                # Reshape para (n_samples, 2) e faz média dos canais
                audio_stereo = audio_int16.reshape(-1, 2)
                audio_mono = audio_stereo.mean(axis=1)
            else:
                audio_mono = audio_int16.astype(np.float64)

            # Converte para float32 (-1.0 a 1.0)
            audio_float = audio_mono.astype(np.float32) / 32768.0

            # Resample de 48kHz para 16kHz usando interpolação de alta qualidade
            if sample_rate != 16000:
                # Calcula número de amostras alvo
                target_samples = int(len(audio_float) * 16000 / sample_rate)

                if target_samples > 0:
                    # Usa interpolação linear de alta qualidade
                    x_old = np.linspace(0, 1, len(audio_float))
                    x_new = np.linspace(0, 1, target_samples)
                    audio_float = np.interp(x_new, x_old, audio_float).astype(np.float32)

            return audio_float

        except Exception as e:
            logger.error(f"Erro ao converter áudio: {e}")
            import traceback
            traceback.print_exc()
            return np.array([], dtype=np.float32)

    def transcribe(self, audio_data: bytes, sample_rate: int = 48000) -> Dict:
        """
        Transcreve áudio para texto.

        Args:
            audio_data: Bytes de áudio (Discord format)
            sample_rate: Taxa de amostragem

        Returns:
            Dict com:
                - text: Texto transcrito
                - language: Idioma detectado
                - confidence: Confiança média
                - segments: Lista de segmentos
        """
        if not WHISPER_AVAILABLE or self._model is None:
            logger.error("Modelo Whisper não disponível!")
            return {
                "text": "",
                "language": self.language,
                "confidence": 0.0,
                "segments": []
            }

        try:
            # Converte áudio para formato Whisper
            audio_np = self.convert_discord_audio(audio_data, sample_rate)

            if len(audio_np) == 0:
                logger.warning("Áudio vazio após conversão")
                return {
                    "text": "",
                    "language": self.language,
                    "confidence": 0.0,
                    "segments": []
                }

            # Transcreve usando Whisper - OTIMIZADO para velocidade
            # initial_prompt ajuda o modelo a entender o contexto
            segments, info = self._model.transcribe(
                audio_np,
                language=self.language,
                task="transcribe",
                vad_filter=True,  # Usa VAD interno do Whisper
                vad_parameters=dict(
                    min_silence_duration_ms=200,  # Reduzido de 300ms
                    speech_pad_ms=400,  # Reduzido de 600ms
                    threshold=0.35  # Ligeiramente mais agressivo
                ),
                beam_size=3,  # Reduzido de 5 (mais rapido)
                best_of=2,  # Reduzido de 5 (mais rapido)
                patience=1.0,  # Reduzido de 2.0 (mais rapido)
                length_penalty=1.0,
                temperature=0.0,  # Mais determinístico
                compression_ratio_threshold=2.4,
                log_prob_threshold=-0.5,
                no_speech_threshold=0.45,  # Ligeiramente mais agressivo
                condition_on_previous_text=False,
                initial_prompt="Conversa portugues. Frases: oi EVE, bom dia, me ajuda, obrigado, tchau."
            )

            # Extrai texto e confiança
            all_text = []
            all_confidences = []
            segment_list = []

            for segment in segments:
                all_text.append(segment.text.strip())
                all_confidences.append(segment.avg_logprob)
                segment_list.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                    "confidence": segment.avg_logprob
                })

            # Junta texto
            full_text = " ".join(all_text).strip()

            # Calcula confiança média
            avg_confidence = np.mean(all_confidences) if all_confidences else 0.0

            # Converte logprob para escala 0-1 (aproximação)
            # Logprob geralmente fica entre -1 e 0
            confidence_normalized = max(0.0, min(1.0, avg_confidence + 1.0))

            result = {
                "text": full_text,
                "language": info.language,
                "confidence": float(confidence_normalized),
                "segments": segment_list
            }

            logger.info(f"Transcrição: '{full_text[:50]}...' (confiança: {confidence_normalized:.2f})")
            return result

        except Exception as e:
            logger.error(f"Erro ao transcrever: {e}")
            import traceback
            traceback.print_exc()
            return {
                "text": "",
                "language": self.language,
                "confidence": 0.0,
                "segments": []
            }

    def transcribe_file(self, audio_file: Path) -> Dict:
        """
        Transcreve arquivo de áudio.

        Args:
            audio_file: Caminho para arquivo de áudio

        Returns:
            Dict com resultado da transcrição
        """
        try:
            # Lê arquivo WAV
            with wave.open(str(audio_file), 'rb') as wav:
                sample_rate = wav.getframerate()
                audio_data = wav.readframes(wav.getnframes())

            return self.transcribe(audio_data, sample_rate)

        except Exception as e:
            logger.error(f"Erro ao transcrever arquivo: {e}")
            return {
                "text": "",
                "language": self.language,
                "confidence": 0.0,
                "segments": []
            }
