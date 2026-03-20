# voice/listener.py - CAPTURA DE VOZ E DETECÇÃO
"""
Sistema de captura de voz do microfone com detecção automática.

Funcionalidades:
- Captura áudio do microfone
- Detecta início e fim da fala usando VAD
- Grava apenas quando há voz (economiza processamento)
- Suporte para gravação contínua ou única
"""

import numpy as np
import logging
import time
import threading
from typing import Optional, Callable
from pathlib import Path

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("⚠️ PyAudio não disponível - captura de microfone desabilitada")

from . import config
from .audio_utils import (
    VoiceActivityDetector,
    normalize_audio,
    reduce_noise,
    trim_silence,
    save_audio,
    get_audio_duration
)

logger = logging.getLogger("eve.voice.listener")


# ═══════════════════════════════════════════════════════════════════
# CLASSE DE CAPTURA DE VOZ
# ═══════════════════════════════════════════════════════════════════

class VoiceListener:
    """
    Captura voz do microfone com detecção automática de fala.

    Usa VAD para detectar quando o usuário começa e para de falar,
    gravando apenas o áudio relevante.
    """

    def __init__(
        self,
        sample_rate: int = config.SAMPLE_RATE,
        chunk_size: int = config.CHUNK_SIZE,
        device_index: Optional[int] = None,
        callback: Optional[Callable] = None
    ):
        """
        Inicializa o listener de voz.

        Args:
            sample_rate: Taxa de amostragem (Hz)
            chunk_size: Tamanho do chunk de áudio
            device_index: Índice do dispositivo de entrada (None = padrão)
            callback: Função chamada quando captura áudio (opcional)
        """
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio não está instalado. Instale com: pip install pyaudio")

        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index
        self.callback = callback

        # Inicializa PyAudio
        self.audio = pyaudio.PyAudio()

        # Stream de áudio
        self.stream = None
        self.is_listening = False
        self.is_recording = False

        # Buffer de gravação
        self.recording_buffer = []

        # VAD (Voice Activity Detection)
        self.vad = VoiceActivityDetector(sample_rate=sample_rate)

        # Controle de timing
        self.speech_start_time = None
        self.silence_start_time = None

        logger.info("✅ VoiceListener inicializado")

    def list_devices(self) -> list:
        """
        Lista todos os dispositivos de áudio disponíveis.

        Returns:
            Lista de dicionários com informações dos dispositivos
        """
        devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:  # Apenas dispositivos de entrada
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info['defaultSampleRate'])
                })
        return devices

    def start_stream(self):
        """Inicia o stream de áudio do microfone."""
        if self.stream is not None:
            logger.warning("Stream já está ativo")
            return

        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=config.CHANNELS,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None  # Modo bloqueante para mais controle
            )
            logger.info("✅ Stream de áudio iniciado")
        except Exception as e:
            logger.error(f"Erro ao iniciar stream: {e}")
            raise

    def stop_stream(self):
        """Para o stream de áudio."""
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.info("Stream de áudio parado")

    def listen_once(
        self,
        timeout: Optional[float] = None,
        save_to: Optional[Path] = None
    ) -> Optional[np.ndarray]:
        """
        Escuta e grava UMA vez (detecta início e fim automaticamente).

        Args:
            timeout: Tempo máximo de espera em segundos (None = infinito)
            save_to: Caminho para salvar o áudio (opcional)

        Returns:
            Array NumPy com o áudio gravado ou None se timeout
        """
        logger.info("🎙️ Aguardando fala...")

        # Inicia stream se necessário
        if self.stream is None:
            self.start_stream()

        # Reseta estado
        self.recording_buffer = []
        self.is_recording = False
        self.speech_start_time = None
        self.silence_start_time = None

        start_time = time.time()

        try:
            while True:
                # Verifica timeout
                if timeout and (time.time() - start_time) > timeout:
                    logger.warning("⏱️ Timeout ao aguardar fala")
                    return None

                # Lê chunk de áudio
                try:
                    audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_chunk = np.frombuffer(audio_data, dtype=np.int16)
                except Exception as e:
                    logger.error(f"Erro ao ler áudio: {e}")
                    continue

                # Detecta voz
                has_speech = self.vad.is_speech(audio_chunk)

                # Máquina de estados: detecta início e fim da fala
                if has_speech:
                    # Voz detectada
                    if not self.is_recording:
                        # Início da gravação
                        logger.info("🔴 Gravando...")
                        self.is_recording = True
                        self.speech_start_time = time.time()

                    # Adiciona ao buffer
                    self.recording_buffer.append(audio_chunk)
                    self.silence_start_time = None  # Reseta contador de silêncio

                elif self.is_recording:
                    # Silêncio durante gravação
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()

                    # Continua gravando (ainda pode voltar a falar)
                    self.recording_buffer.append(audio_chunk)

                    # Verifica se silêncio foi longo o suficiente para parar
                    silence_duration = time.time() - self.silence_start_time
                    if silence_duration >= config.SILENCE_DURATION:
                        # Verifica se falou tempo mínimo
                        speech_duration = time.time() - self.speech_start_time
                        if speech_duration >= config.MIN_SPEECH_DURATION:
                            logger.info(f"⏹️ Gravação finalizada ({speech_duration:.1f}s)")
                            break
                        else:
                            # Falso positivo (falou muito pouco)
                            logger.debug("Falso positivo - reiniciando")
                            self.recording_buffer = []
                            self.is_recording = False
                            self.silence_start_time = None

                # Verifica duração máxima
                if self.is_recording:
                    duration = time.time() - self.speech_start_time
                    if duration >= config.MAX_RECORDING_DURATION:
                        logger.warning(f"⚠️ Duração máxima atingida ({duration:.1f}s)")
                        break

        except KeyboardInterrupt:
            logger.info("Gravação interrompida pelo usuário")
            return None

        # Processa áudio gravado
        if not self.recording_buffer:
            logger.warning("Nenhum áudio gravado")
            return None

        # Concatena todos os chunks
        audio = np.concatenate(self.recording_buffer)

        # Pós-processamento
        audio_float = audio.astype(np.float32) / 32768.0

        if config.USE_AUDIO_ENHANCEMENT:
            # Remove silêncio das pontas
            audio_float = trim_silence(audio_float, self.sample_rate)

            # Reduz ruído
            audio_float = reduce_noise(audio_float, self.sample_rate)

            # Normaliza volume
            audio_float = normalize_audio(audio_float)

        # Salva se solicitado
        if save_to:
            save_audio(audio_float, save_to, self.sample_rate)

        # Callback
        if self.callback:
            try:
                self.callback(audio_float)
            except Exception as e:
                logger.error(f"Erro no callback: {e}")

        duration = get_audio_duration(audio_float, self.sample_rate)
        logger.info(f"✅ Áudio capturado: {duration:.2f}s")

        return audio_float

    def listen_continuous(
        self,
        on_audio: Callable[[np.ndarray], None],
        stop_event: Optional[threading.Event] = None
    ):
        """
        Escuta continuamente e chama callback a cada fala detectada.

        Args:
            on_audio: Função chamada quando detecta uma fala completa
            stop_event: Evento para parar a escuta (opcional)
        """
        logger.info("🎙️ Modo de escuta contínua ativado (Ctrl+C para parar)")

        # Inicia stream se necessário
        if self.stream is None:
            self.start_stream()

        self.is_listening = True

        try:
            while self.is_listening:
                # Verifica evento de parada
                if stop_event and stop_event.is_set():
                    break

                # Escuta uma vez
                audio = self.listen_once()

                if audio is not None:
                    # Chama callback em thread separada para não bloquear
                    thread = threading.Thread(target=on_audio, args=(audio,))
                    thread.daemon = True
                    thread.start()

        except KeyboardInterrupt:
            logger.info("Escuta contínua interrompida")
        finally:
            self.is_listening = False

    def stop_listening(self):
        """Para a escuta contínua."""
        self.is_listening = False
        logger.info("Escuta parada")

    def cleanup(self):
        """Libera recursos."""
        self.stop_stream()
        if self.audio:
            self.audio.terminate()
        logger.info("Recursos liberados")

    def __enter__(self):
        """Context manager: entrada"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: saída"""
        self.cleanup()


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

def list_microphones() -> list:
    """
    Lista todos os microfones disponíveis.

    Returns:
        Lista de dicionários com informações dos microfones
    """
    if not PYAUDIO_AVAILABLE:
        logger.error("PyAudio não disponível")
        return []

    listener = VoiceListener()
    devices = listener.list_devices()
    listener.cleanup()
    return devices


def record_audio(
    duration: Optional[float] = None,
    timeout: Optional[float] = None,
    device_index: Optional[int] = None,
    save_to: Optional[Path] = None
) -> Optional[np.ndarray]:
    """
    Grava áudio do microfone (função de conveniência).

    Args:
        duration: Duração fixa em segundos (None = detecção automática)
        timeout: Timeout em segundos
        device_index: Índice do dispositivo
        save_to: Caminho para salvar

    Returns:
        Array NumPy com áudio ou None
    """
    with VoiceListener(device_index=device_index) as listener:
        if duration:
            # Gravação com duração fixa (sem VAD)
            logger.info(f"🎙️ Gravando por {duration}s...")
            listener.start_stream()

            frames = int(duration * config.SAMPLE_RATE / config.CHUNK_SIZE)
            audio_chunks = []

            for _ in range(frames):
                data = listener.stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                chunk = np.frombuffer(data, dtype=np.int16)
                audio_chunks.append(chunk)

            audio = np.concatenate(audio_chunks).astype(np.float32) / 32768.0

            if save_to:
                save_audio(audio, save_to, config.SAMPLE_RATE)

            return audio
        else:
            # Gravação com detecção automática (VAD)
            return listener.listen_once(timeout=timeout, save_to=save_to)


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Lista microfones
    print("📋 Microfones disponíveis:")
    mics = list_microphones()
    for mic in mics:
        print(f"  [{mic['index']}] {mic['name']} - {mic['sample_rate']}Hz")

    # Teste de gravação
    print("\n🎙️ Teste de gravação (fale algo)...")
    audio = record_audio(save_to=config.CACHE_DIR / "test_recording.wav")

    if audio is not None:
        duration = get_audio_duration(audio)
        print(f"✅ Gravado: {duration:.2f}s")
    else:
        print("❌ Nenhum áudio capturado")
