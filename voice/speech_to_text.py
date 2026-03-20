# voice/speech_to_text.py - RECONHECIMENTO DE VOZ (STT)
"""
Sistema de Speech-to-Text usando Whisper.

Funcionalidades:
- Transcrição de áudio usando OpenAI Whisper
- Suporte para faster-whisper (otimizado)
- Detecção automática de idioma
- Cache de transcrições
- Suporte para múltiplos formatos de áudio
"""

import numpy as np
import logging
import hashlib
import json
from typing import Optional, Union, Dict
from pathlib import Path

# Tenta importar faster-whisper (recomendado)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("⚠️ faster-whisper não disponível - tentando whisper padrão")

# Fallback para whisper padrão
if not FASTER_WHISPER_AVAILABLE:
    try:
        import whisper
        WHISPER_AVAILABLE = True
    except ImportError:
        WHISPER_AVAILABLE = False
        print("⚠️ whisper não disponível - STT desabilitado")

from . import config
from .audio_utils import save_audio, load_audio

logger = logging.getLogger("eve.voice.stt")


# ═══════════════════════════════════════════════════════════════════
# CLASSE DE SPEECH-TO-TEXT
# ═══════════════════════════════════════════════════════════════════

class SpeechToText:
    """
    Converte áudio em texto usando Whisper.

    Suporta tanto faster-whisper (otimizado) quanto whisper padrão.
    """

    def __init__(
        self,
        model_name: str = config.WHISPER_MODEL,
        language: str = config.WHISPER_LANGUAGE,
        device: str = config.WHISPER_DEVICE,
        compute_type: str = config.WHISPER_COMPUTE_TYPE,
        use_cache: bool = config.ENABLE_TRANSCRIPTION_CACHE
    ):
        """
        Inicializa o sistema de STT.

        Args:
            model_name: Nome do modelo Whisper (tiny, base, small, medium, large-v3)
            language: Código do idioma (pt, en, etc.)
            device: Dispositivo ("cpu", "cuda" ou "auto")
            compute_type: Tipo de computação ("float32", "float16", "int8")
            use_cache: Se deve usar cache de transcrições
        """
        if not FASTER_WHISPER_AVAILABLE and not WHISPER_AVAILABLE:
            raise RuntimeError(
                "Whisper não está instalado. Instale com:\n"
                "  pip install faster-whisper  (recomendado)\n"
                "ou\n"
                "  pip install openai-whisper"
            )

        self.model_name = model_name
        self.language = language
        self.use_cache = use_cache
        self.model = None

        # Detecta dispositivo automaticamente
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"🔍 Device auto-detectado: {device}")
            except ImportError:
                device = "cpu"
                logger.info("PyTorch não disponível - usando CPU")

        self.device = device
        self.compute_type = compute_type

        # Diretório de cache
        self.cache_dir = config.CACHE_DIR / "transcriptions"
        self.cache_dir.mkdir(exist_ok=True)

        # Carrega modelo
        self._load_model()

    def _load_model(self):
        """Carrega o modelo Whisper."""
        logger.info(f"Carregando modelo Whisper: {self.model_name} ({self.device})...")

        try:
            if FASTER_WHISPER_AVAILABLE:
                # faster-whisper (recomendado - mais rápido e eficiente)
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=str(config.MODELS_DIR)
                )
                self.using_faster_whisper = True
                logger.info("✅ faster-whisper carregado com sucesso")
            else:
                # whisper padrão (fallback)
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device,
                    download_root=str(config.MODELS_DIR)
                )
                self.using_faster_whisper = False
                logger.info("✅ whisper padrão carregado com sucesso")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            raise

    def _get_cache_key(self, audio: np.ndarray) -> str:
        """
        Gera uma chave de cache única para o áudio.

        Args:
            audio: Array NumPy com áudio

        Returns:
            Hash MD5 do áudio
        """
        # Converte para bytes e calcula hash
        audio_bytes = audio.tobytes()
        return hashlib.md5(audio_bytes).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """
        Carrega transcrição do cache.

        Args:
            cache_key: Chave do cache

        Returns:
            Dicionário com transcrição ou None
        """
        if not self.use_cache:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Erro ao carregar cache: {e}")

        return None

    def _save_to_cache(self, cache_key: str, result: Dict):
        """
        Salva transcrição no cache.

        Args:
            cache_key: Chave do cache
            result: Dicionário com resultado
        """
        if not self.use_cache:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")

    def transcribe(
        self,
        audio: Union[np.ndarray, str, Path],
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = config.WHISPER_BEAM_SIZE,
        temperature: float = 0.0
    ) -> Dict[str, any]:
        """
        Transcreve áudio para texto.

        Args:
            audio: Array NumPy, caminho de arquivo ou bytes
            language: Código do idioma (None = auto-detectar)
            task: "transcribe" ou "translate" (traduzir para inglês)
            beam_size: Tamanho do beam search (1 = greedy, mais rápido)
            temperature: Temperatura de amostragem (0.0 = determinístico)

        Returns:
            Dicionário com:
                - text: Texto transcrito
                - language: Idioma detectado
                - confidence: Confiança média
                - segments: Lista de segmentos (opcional)
        """
        # Carrega áudio se for caminho
        if isinstance(audio, (str, Path)):
            audio_path = Path(audio)
            if not audio_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

            audio, sample_rate = load_audio(audio_path, target_sr=config.SAMPLE_RATE)
        elif isinstance(audio, np.ndarray):
            # Já é array NumPy
            pass
        else:
            raise TypeError("audio deve ser np.ndarray, str ou Path")

        # Verifica cache
        cache_key = self._get_cache_key(audio)
        cached = self._load_from_cache(cache_key)
        if cached:
            logger.info("✨ Transcrição do cache")
            return cached

        # Usa idioma especificado ou padrão
        lang = language or self.language

        logger.info(f"🎙️ Transcrevendo áudio ({len(audio) / config.SAMPLE_RATE:.1f}s)...")

        try:
            if self.using_faster_whisper:
                # faster-whisper
                result = self._transcribe_faster_whisper(
                    audio, lang, task, beam_size, temperature
                )
            else:
                # whisper padrão
                result = self._transcribe_whisper(
                    audio, lang, task
                )

            # Salva no cache
            self._save_to_cache(cache_key, result)

            logger.info(f"✅ Transcrição: {result['text'][:100]}...")
            return result

        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            return {
                "text": "",
                "language": lang,
                "confidence": 0.0,
                "error": str(e)
            }

    def _transcribe_faster_whisper(
        self,
        audio: np.ndarray,
        language: str,
        task: str,
        beam_size: int,
        temperature: float
    ) -> Dict:
        """
        Transcreve usando faster-whisper.

        Args:
            audio: Array NumPy com áudio
            language: Idioma
            task: Tarefa
            beam_size: Beam size
            temperature: Temperatura

        Returns:
            Dicionário com resultado
        """
        # faster-whisper espera float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Transcreve
        segments, info = self.model.transcribe(
            audio,
            language=language if not config.WHISPER_AUTO_DETECT_LANGUAGE else None,
            task=task,
            beam_size=beam_size,
            temperature=temperature,
            vad_filter=True,  # Usa VAD interno
            vad_parameters=dict(
                threshold=config.SILERO_THRESHOLD,
                min_speech_duration_ms=int(config.MIN_SPEECH_DURATION * 1000)
            )
        )

        # Extrai informações
        text_segments = []
        full_text = []
        total_confidence = 0.0
        segment_count = 0

        for segment in segments:
            text_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob  # Aproximação de confiança
            })
            full_text.append(segment.text.strip())
            total_confidence += segment.avg_logprob
            segment_count += 1

        avg_confidence = total_confidence / segment_count if segment_count > 0 else 0.0

        return {
            "text": " ".join(full_text),
            "language": info.language,
            "confidence": avg_confidence,
            "segments": text_segments
        }

    def _transcribe_whisper(
        self,
        audio: np.ndarray,
        language: str,
        task: str
    ) -> Dict:
        """
        Transcreve usando whisper padrão.

        Args:
            audio: Array NumPy com áudio
            language: Idioma
            task: Tarefa

        Returns:
            Dicionário com resultado
        """
        # whisper padrão espera float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Transcreve
        result = self.model.transcribe(
            audio,
            language=language if not config.WHISPER_AUTO_DETECT_LANGUAGE else None,
            task=task,
            fp16=(self.device == "cuda")
        )

        # Processa segmentos
        text_segments = []
        for seg in result.get("segments", []):
            text_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "confidence": seg.get("avg_logprob", 0.0)
            })

        return {
            "text": result["text"].strip(),
            "language": result.get("language", language),
            "confidence": 0.0,  # whisper padrão não fornece confiança global
            "segments": text_segments
        }

    def transcribe_file(self, filepath: Union[str, Path], **kwargs) -> Dict:
        """
        Transcreve arquivo de áudio.

        Args:
            filepath: Caminho do arquivo
            **kwargs: Argumentos passados para transcribe()

        Returns:
            Dicionário com resultado
        """
        return self.transcribe(filepath, **kwargs)

    def get_model_info(self) -> Dict:
        """
        Retorna informações sobre o modelo carregado.

        Returns:
            Dicionário com informações
        """
        return {
            "model_name": self.model_name,
            "language": self.language,
            "device": self.device,
            "compute_type": self.compute_type,
            "using_faster_whisper": self.using_faster_whisper,
            "cache_enabled": self.use_cache
        }


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

# Instância global (lazy loading)
_stt_instance: Optional[SpeechToText] = None


def get_stt() -> SpeechToText:
    """
    Retorna instância global do STT (singleton).

    Returns:
        Instância de SpeechToText
    """
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText()
    return _stt_instance


def transcribe(audio: Union[np.ndarray, str, Path], **kwargs) -> str:
    """
    Transcreve áudio para texto (função de conveniência).

    Args:
        audio: Array NumPy ou caminho de arquivo
        **kwargs: Argumentos extras

    Returns:
        Texto transcrito
    """
    stt = get_stt()
    result = stt.transcribe(audio, **kwargs)
    return result.get("text", "")


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Teste básico
    print("Testando Speech-to-Text...")

    stt = SpeechToText(model_name="tiny")  # Modelo pequeno para teste rápido
    print(f"Modelo carregado: {stt.get_model_info()}")

    # Testa com áudio de teste (se existir)
    test_file = config.CACHE_DIR / "test_recording.wav"
    if test_file.exists():
        print(f"\nTranscrevendo: {test_file}")
        result = stt.transcribe(test_file)
        print(f"Texto: {result['text']}")
        print(f"Idioma: {result['language']}")
        print(f"Confiança: {result['confidence']:.2f}")
    else:
        print(f"\nArquivo de teste não encontrado: {test_file}")

    print("✅ Testes concluídos!")
