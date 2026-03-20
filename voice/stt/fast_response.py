# voice/stt/fast_response.py - Sistema de Resposta Rapida
"""
Otimizacoes para respostas mais rapidas:

1. Deteccao de silencio mais rapida (0.8s ao inves de 1.5s)
2. Transcricao adaptativa (rapida vs precisa)
3. Classificacao de complexidade da pergunta
"""

import logging
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("eve.voice.fast_response")


class ResponseSpeed(Enum):
    """Velocidade de resposta"""
    INSTANT = "instant"     # Saudacoes, sim/nao - resposta imediata
    FAST = "fast"           # Perguntas simples - transcricao rapida
    NORMAL = "normal"       # Perguntas normais - transcricao padrao
    CAREFUL = "careful"     # Perguntas complexas - transcricao cuidadosa


@dataclass
class FastResponseConfig:
    """Configuracao para respostas rapidas"""

    # === Deteccao de silencio ===
    silence_instant: float = 0.5    # Para saudacoes curtas
    silence_fast: float = 0.8       # Para perguntas simples
    silence_normal: float = 1.2     # Padrao
    silence_careful: float = 1.8    # Para perguntas longas

    # === Transcricao ===
    beam_size_fast: int = 1         # Mais rapido
    beam_size_normal: int = 3       # Equilibrado
    beam_size_careful: int = 5      # Mais preciso

    # === Audio minimo ===
    min_audio_instant: float = 0.3  # Minimo para "oi"
    min_audio_fast: float = 0.5     # Minimo para perguntas curtas
    min_audio_normal: float = 0.8   # Padrao


class QuestionClassifier:
    """
    Classifica perguntas para determinar velocidade de resposta.

    Baseado em:
    - Comprimento do audio
    - Palavras-chave detectadas
    - Complexidade estimada
    """

    # Padroes para respostas instantaneas (saudacoes, confirmacoes)
    INSTANT_PATTERNS = [
        r'^(oi|ola|hey|hi|e ai)\s*[!.?]*$',
        r'^(bom dia|boa tarde|boa noite)\s*[!.?]*$',
        r'^(sim|nao|ta|ok|certo|entendi)\s*[!.?]*$',
        r'^(obrigad[oa]|valeu|brigad[oa])\s*[!.?]*$',
        r'^(tchau|ate|bye|fui)\s*[!.?]*$',
    ]

    # Padroes para respostas rapidas (perguntas simples)
    FAST_PATTERNS = [
        r'^(que horas|qual hora)',
        r'^(como voce esta|tudo bem)',
        r'^(o que e|quem e)\s+\w+\s*[?]?$',
        r'^(voce pode|pode)\s+\w+\s*[?]?$',
    ]

    # Padroes para respostas cuidadosas (perguntas complexas)
    CAREFUL_PATTERNS = [
        r'(explique|explica|me ensina|me conta)',
        r'(como funciona|por que|porque)',
        r'(crie|escreva|implemente|desenvolva).*codigo',
        r'(passo a passo|detalhad)',
        r'(analise|compare|avalie)',
    ]

    def __init__(self):
        # Compila padroes para performance
        self._instant_compiled = [re.compile(p, re.IGNORECASE) for p in self.INSTANT_PATTERNS]
        self._fast_compiled = [re.compile(p, re.IGNORECASE) for p in self.FAST_PATTERNS]
        self._careful_compiled = [re.compile(p, re.IGNORECASE) for p in self.CAREFUL_PATTERNS]

    def classify_by_audio_duration(self, duration_seconds: float) -> ResponseSpeed:
        """
        Classifica baseado na duracao do audio.

        Heuristica: audio curto = pergunta simples
        """
        if duration_seconds < 1.0:
            return ResponseSpeed.INSTANT
        elif duration_seconds < 2.0:
            return ResponseSpeed.FAST
        elif duration_seconds < 5.0:
            return ResponseSpeed.NORMAL
        else:
            return ResponseSpeed.CAREFUL

    def classify_by_text(self, text: str) -> ResponseSpeed:
        """
        Classifica baseado no texto transcrito.

        Usado para ajustar resposta apos transcricao.
        """
        text_lower = text.lower().strip()

        # Verifica padroes instantaneos
        for pattern in self._instant_compiled:
            if pattern.match(text_lower):
                return ResponseSpeed.INSTANT

        # Verifica padroes rapidos
        for pattern in self._fast_compiled:
            if pattern.search(text_lower):
                return ResponseSpeed.FAST

        # Verifica padroes cuidadosos
        for pattern in self._careful_compiled:
            if pattern.search(text_lower):
                return ResponseSpeed.CAREFUL

        # Baseado em comprimento
        word_count = len(text.split())
        if word_count <= 3:
            return ResponseSpeed.FAST
        elif word_count <= 10:
            return ResponseSpeed.NORMAL
        else:
            return ResponseSpeed.CAREFUL

    def classify(
        self,
        audio_duration: Optional[float] = None,
        text: Optional[str] = None
    ) -> ResponseSpeed:
        """
        Classifica usando todas as informacoes disponiveis.

        Args:
            audio_duration: Duracao do audio em segundos
            text: Texto transcrito (se disponivel)

        Returns:
            ResponseSpeed indicando velocidade recomendada
        """
        # Se temos texto, usar classificacao por texto (mais precisa)
        if text:
            return self.classify_by_text(text)

        # Senao, usar duracao do audio
        if audio_duration:
            return self.classify_by_audio_duration(audio_duration)

        # Default
        return ResponseSpeed.NORMAL


class AdaptiveTranscriber:
    """
    Wrapper para AudioTranscriber com configuracao adaptativa.

    Ajusta parametros baseado na complexidade esperada.
    """

    def __init__(self, base_transcriber):
        """
        Args:
            base_transcriber: AudioTranscriber base
        """
        self.transcriber = base_transcriber
        self.classifier = QuestionClassifier()
        self.config = FastResponseConfig()

    def get_transcribe_params(self, speed: ResponseSpeed) -> Dict:
        """
        Retorna parametros de transcricao para a velocidade.

        Args:
            speed: Velocidade desejada

        Returns:
            Dict de parametros para Whisper
        """
        if speed == ResponseSpeed.INSTANT:
            return {
                'beam_size': 1,
                'best_of': 1,
                'patience': 0.5,
                'temperature': 0.0,
            }
        elif speed == ResponseSpeed.FAST:
            return {
                'beam_size': 2,
                'best_of': 2,
                'patience': 1.0,
                'temperature': 0.0,
            }
        elif speed == ResponseSpeed.CAREFUL:
            return {
                'beam_size': 5,
                'best_of': 5,
                'patience': 2.0,
                'temperature': 0.0,
            }
        else:  # NORMAL
            return {
                'beam_size': 3,
                'best_of': 3,
                'patience': 1.5,
                'temperature': 0.0,
            }

    def get_silence_duration(self, audio_duration: float) -> float:
        """
        Retorna duracao de silencio apropriada.

        Audio curto = espera menos silencio para processar.
        """
        speed = self.classifier.classify_by_audio_duration(audio_duration)

        if speed == ResponseSpeed.INSTANT:
            return self.config.silence_instant
        elif speed == ResponseSpeed.FAST:
            return self.config.silence_fast
        elif speed == ResponseSpeed.CAREFUL:
            return self.config.silence_careful
        else:
            return self.config.silence_normal


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACOES OTIMIZADAS PARA O SINK
# ═══════════════════════════════════════════════════════════════════

class OptimizedSinkConfig:
    """
    Configuracoes otimizadas para VoiceRecordingSink.

    Use estas configuracoes para respostas mais rapidas.
    """

    # Silencio reduzido (0.8s ao inves de 1.5s)
    MAX_SILENCE_DURATION = 0.8

    # Audio minimo menor (permite "oi" rapido)
    MIN_AUDIO_DURATION = 0.3

    # VAD mais sensivel
    VAD_ENERGY_THRESHOLD = 0.002

    @classmethod
    def apply_to_sink(cls, sink):
        """
        Aplica configuracoes otimizadas a um sink existente.

        Args:
            sink: VoiceRecordingSink para otimizar
        """
        sink.max_silence_duration = cls.MAX_SILENCE_DURATION
        sink.min_audio_duration = cls.MIN_AUDIO_DURATION
        if hasattr(sink, 'vad'):
            sink.vad.energy_threshold = cls.VAD_ENERGY_THRESHOLD

        logger.info(f"⚡ Sink otimizado: silencio={cls.MAX_SILENCE_DURATION}s, "
                   f"min_audio={cls.MIN_AUDIO_DURATION}s")


# ═══════════════════════════════════════════════════════════════════
# INSTANCIAS GLOBAIS
# ═══════════════════════════════════════════════════════════════════

_classifier: Optional[QuestionClassifier] = None


def get_classifier() -> QuestionClassifier:
    """Retorna classificador global"""
    global _classifier
    if _classifier is None:
        _classifier = QuestionClassifier()
    return _classifier


def classify_question(
    audio_duration: float = None,
    text: str = None
) -> ResponseSpeed:
    """Shortcut para classificar pergunta"""
    return get_classifier().classify(audio_duration, text)
