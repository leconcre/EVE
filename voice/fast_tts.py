# voice/fast_tts.py - ENGINE TTS OTIMIZADO PARA BAIXA LATENCIA
"""
Engine de TTS otimizado para respostas rapidas.

Otimizacoes:
1. Streaming de audio (começa a tocar antes de terminar de gerar)
2. Cache de frases comuns
3. Taxa de fala aumentada
4. Pre-aquecimento de conexao
"""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, Callable, AsyncGenerator
from dataclasses import dataclass
import time
import threading

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

from . import config

logger = logging.getLogger("eve.voice.fast_tts")


@dataclass
class TTSMetrics:
    """Metricas de performance do TTS"""
    synthesis_time_ms: int = 0
    audio_duration_ms: int = 0
    cache_hit: bool = False
    chunks_streamed: int = 0


class FastTTS:
    """
    Engine TTS otimizado para baixa latencia.

    Principais otimizacoes:
    - Streaming: comeca a reproduzir enquanto ainda gera
    - Cache: frases comuns pre-geradas
    - Velocidade normal: mantem voz natural
    """

    # Frases comuns para cache
    COMMON_PHRASES = [
        "Oi!",
        "Olá!",
        "Certo!",
        "Entendi!",
        "Hmm, deixa eu pensar...",
        "Só um momento...",
        "Pronto!",
        "Desculpa, não entendi.",
        "Pode repetir?",
        "Tá bom!",
        "Vou verificar...",
        "Interessante!",
    ]

    def __init__(
        self,
        voice: str = "pt-BR-FranciscaNeural",
        rate: str = "+0%",  # Velocidade normal (natural)
        volume: str = "+0%",
        pitch: str = "+0Hz",
        cache_dir: Optional[Path] = None,
        preload_cache: bool = True
    ):
        """
        Inicializa Fast TTS.

        Args:
            voice: Voz do Edge TTS
            rate: Taxa de fala (+25% = mais rapido mas natural)
            volume: Volume
            pitch: Pitch
            cache_dir: Diretorio para cache de audio
            preload_cache: Se deve pre-gerar frases comuns
        """
        if not EDGE_TTS_AVAILABLE:
            raise RuntimeError("edge-tts não instalado")

        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self.cache_dir = cache_dir or config.CACHE_DIR / "tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Lock para acesso thread-safe ao cache
        self._cache_lock = threading.RLock()

        # Cache em memoria (hash -> path do arquivo)
        self._cache: Dict[str, Path] = {}

        # Carregar cache existente
        self._load_cache_index()

        # Pre-aquecer cache em background
        if preload_cache:
            asyncio.create_task(self._preload_common_phrases())

        logger.info(f"✅ Fast TTS inicializado (rate={rate}, voice={voice})")

    def _get_cache_key(self, text: str) -> str:
        """Gera chave de cache para texto"""
        # Inclui parametros de voz na chave
        key_data = f"{text}|{self.voice}|{self.rate}|{self.pitch}"
        return hashlib.md5(key_data.encode()).hexdigest()[:12]

    def _load_cache_index(self):
        """Carrega indice de arquivos cacheados (thread-safe)"""
        with self._cache_lock:
            for mp3_file in self.cache_dir.glob("*.mp3"):
                # Nome do arquivo e a chave de cache
                self._cache[mp3_file.stem] = mp3_file
            logger.info(f"📦 Cache carregado: {len(self._cache)} arquivos")

    async def _preload_common_phrases(self):
        """Pre-gera frases comuns em background (thread-safe)"""
        logger.info("🔄 Pre-gerando frases comuns...")
        for phrase in self.COMMON_PHRASES:
            cache_key = self._get_cache_key(phrase)
            # Verifica se já existe no cache (thread-safe)
            with self._cache_lock:
                already_cached = cache_key in self._cache
            if not already_cached:
                try:
                    await self.synthesize_to_file(phrase)
                except Exception as e:
                    logger.warning(f"Erro ao pre-gerar '{phrase}': {e}")
        with self._cache_lock:
            cache_size = len(self._cache)
        logger.info(f"✅ Cache de frases comum pronto ({cache_size} total)")

    async def synthesize_to_file(
        self,
        text: str,
        output_file: Optional[Path] = None
    ) -> tuple[Path, TTSMetrics]:
        """
        Sintetiza texto para arquivo MP3 (thread-safe).

        Args:
            text: Texto para sintetizar
            output_file: Arquivo de saida (opcional, usa cache)

        Returns:
            (path do arquivo, metricas)
        """
        start_time = time.time()
        metrics = TTSMetrics()

        # Verificar cache (thread-safe)
        cache_key = self._get_cache_key(text)
        with self._cache_lock:
            if cache_key in self._cache:
                cached_file = self._cache[cache_key]
                if cached_file.exists():
                    metrics.cache_hit = True
                    metrics.synthesis_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"⚡ Cache hit: {text[:30]}...")
                    return cached_file, metrics

        # Definir arquivo de saida
        if output_file is None:
            output_file = self.cache_dir / f"{cache_key}.mp3"

        # Sintetizar (fora do lock para não bloquear)
        try:
            communicate = edge_tts.Communicate(
                text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch
            )

            await communicate.save(str(output_file))

            # Adicionar ao cache (thread-safe)
            with self._cache_lock:
                self._cache[cache_key] = output_file

            metrics.synthesis_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ Sintetizado em {metrics.synthesis_time_ms}ms: {text[:30]}...")

            return output_file, metrics

        except Exception as e:
            logger.error(f"Erro ao sintetizar: {e}")
            raise

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[bytes], None] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Sintetiza texto com streaming de chunks.

        Permite comecar a reproduzir ANTES do audio estar completo.

        Args:
            text: Texto para sintetizar
            on_chunk: Callback chamado para cada chunk

        Yields:
            Chunks de audio MP3
        """
        start_time = time.time()
        chunks_count = 0

        try:
            communicate = edge_tts.Communicate(
                text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch
            )

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks_count += 1
                    audio_data = chunk["data"]

                    if on_chunk:
                        on_chunk(audio_data)

                    yield audio_data

            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"✅ Streaming completo: {chunks_count} chunks em {elapsed}ms")

        except Exception as e:
            logger.error(f"Erro no streaming: {e}")
            raise

    async def synthesize_streaming_to_file(
        self,
        text: str,
        output_file: Path
    ) -> TTSMetrics:
        """
        Sintetiza com streaming salvando em arquivo.

        Mais rapido que synthesize_to_file para textos longos.
        """
        start_time = time.time()
        metrics = TTSMetrics()

        try:
            with open(output_file, 'wb') as f:
                async for chunk in self.synthesize_streaming(text):
                    f.write(chunk)
                    metrics.chunks_streamed += 1

            metrics.synthesis_time_ms = int((time.time() - start_time) * 1000)
            return metrics

        except Exception as e:
            logger.error(f"Erro ao salvar streaming: {e}")
            raise

    def get_cached_file(self, text: str) -> Optional[Path]:
        """
        Retorna arquivo cacheado se existir (thread-safe).

        Util para verificar se uma frase ja foi gerada.
        """
        cache_key = self._get_cache_key(text)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and cached.exists():
                return cached
        return None

    def clear_cache(self, older_than_days: int = 7):
        """Remove arquivos de cache antigos (thread-safe)"""
        import time as time_module
        now = time_module.time()
        removed = 0

        for cache_file in self.cache_dir.glob("*.mp3"):
            age_days = (now - cache_file.stat().st_mtime) / 86400
            if age_days > older_than_days:
                try:
                    cache_file.unlink()
                    removed += 1
                except OSError:
                    pass

        # Recarregar indice (já é thread-safe)
        with self._cache_lock:
            self._cache.clear()
        self._load_cache_index()

        logger.info(f"🧹 Cache limpo: {removed} arquivos removidos")

    def get_stats(self) -> Dict:
        """Retorna estatisticas do TTS (thread-safe)"""
        with self._cache_lock:
            cache_size = len(self._cache)
        return {
            'voice': self.voice,
            'rate': self.rate,
            'cache_size': cache_size,
            'cache_dir': str(self.cache_dir)
        }


# ═══════════════════════════════════════════════════════════════════
# WRAPPER PARA DISCORD
# ═══════════════════════════════════════════════════════════════════

class DiscordFastTTS:
    """
    TTS otimizado para uso com Discord.

    Gera arquivos MP3 prontos para FFmpegPCMAudio.
    """

    def __init__(
        self,
        voice: str = "pt-BR-FranciscaNeural",
        rate: str = "+25%"
    ):
        self.tts = FastTTS(voice=voice, rate=rate)
        self._temp_file = config.CACHE_DIR / "discord_tts_temp.mp3"

    async def speak(self, text: str) -> Path:
        """
        Gera audio para reproduzir no Discord.

        Args:
            text: Texto para falar

        Returns:
            Path do arquivo MP3
        """
        # Verifica cache primeiro
        cached = self.tts.get_cached_file(text)
        if cached:
            return cached

        # Gera novo
        audio_file, metrics = await self.tts.synthesize_to_file(text)
        return audio_file

    async def speak_streaming(
        self,
        text: str,
        output_file: Optional[Path] = None
    ) -> Path:
        """
        Gera audio com streaming (mais rapido para textos longos).
        """
        output_file = output_file or self._temp_file
        await self.tts.synthesize_streaming_to_file(text, output_file)
        return output_file


# ═══════════════════════════════════════════════════════════════════
# INSTANCIA GLOBAL
# ═══════════════════════════════════════════════════════════════════

_fast_tts: Optional[FastTTS] = None
_discord_tts: Optional[DiscordFastTTS] = None


def get_fast_tts(
    rate: str = "+25%",
    voice: str = "pt-BR-FranciscaNeural"
) -> FastTTS:
    """Retorna instancia global do Fast TTS"""
    global _fast_tts
    if _fast_tts is None:
        _fast_tts = FastTTS(rate=rate, voice=voice)
    return _fast_tts


def get_discord_tts(
    rate: str = "+25%",
    voice: str = "pt-BR-FranciscaNeural"
) -> DiscordFastTTS:
    """Retorna instancia global do Discord TTS"""
    global _discord_tts
    if _discord_tts is None:
        _discord_tts = DiscordFastTTS(rate=rate, voice=voice)
    return _discord_tts


# ═══════════════════════════════════════════════════════════════════
# TESTE
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    async def test():
        print("🧪 Testando Fast TTS...")

        tts = FastTTS(rate="+30%")  # 30% mais rapido

        # Teste 1: Sintese normal
        print("\n1. Sintese normal:")
        text = "Ola! Eu sou a EVE, sua assistente virtual."
        file, metrics = await tts.synthesize_to_file(text)
        print(f"   Arquivo: {file}")
        print(f"   Tempo: {metrics.synthesis_time_ms}ms")
        print(f"   Cache hit: {metrics.cache_hit}")

        # Teste 2: Cache hit
        print("\n2. Cache hit (mesma frase):")
        file, metrics = await tts.synthesize_to_file(text)
        print(f"   Tempo: {metrics.synthesis_time_ms}ms")
        print(f"   Cache hit: {metrics.cache_hit}")

        # Teste 3: Streaming
        print("\n3. Streaming:")
        chunks = 0
        async for chunk in tts.synthesize_streaming("Teste de streaming de audio."):
            chunks += 1
        print(f"   Chunks recebidos: {chunks}")

        print("\n✅ Testes concluidos!")
        print(f"📊 Stats: {tts.get_stats()}")

    asyncio.run(test())
