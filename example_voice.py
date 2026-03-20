# example_voice.py - EXEMPLO DE USO DO MÓDULO DE VOZ COM EVE
"""
Exemplos de como usar o módulo de voz com a EVE.

Executar:
    python example_voice.py --mode simple
    python example_voice.py --mode advanced
    python example_voice.py --mode discord
"""

import argparse
import sys
import logging
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.eve import Eve
from voice import listen, speak, create_voice_loop, cleanup, get_info

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("example_voice")


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO 1: USO SIMPLES
# ═══════════════════════════════════════════════════════════════════

def example_simple():
    """
    Exemplo mais simples possível: ouvir e falar.
    """
    print("=" * 60)
    print("EXEMPLO 1: Uso Simples")
    print("=" * 60)
    print("\nEste exemplo demonstra o uso básico:")
    print("1. Ouve sua voz")
    print("2. Mostra o texto")
    print("3. Responde falando")
    print("\nPressione Ctrl+C para parar\n")

    try:
        # Ouve
        print("🎙️ Fale algo...")
        text = listen()

        if text:
            print(f"\n✅ Você disse: {text}\n")

            # Responde
            response = f"Você disse: {text}"
            print(f"🔊 EVE: {response}\n")
            speak(response)
        else:
            print("❌ Nenhum texto capturado")

    except KeyboardInterrupt:
        print("\n\n👋 Exemplo finalizado!")
    finally:
        cleanup()


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO 2: INTEGRAÇÃO COMPLETA COM EVE
# ═══════════════════════════════════════════════════════════════════

def example_with_eve():
    """
    Exemplo de integração completa com a EVE.
    """
    print("=" * 60)
    print("EXEMPLO 2: Integração Completa com EVE")
    print("=" * 60)
    print("\nEste exemplo:")
    print("1. Ouve sua pergunta")
    print("2. Processa com a EVE")
    print("3. Responde falando")
    print("\nPressione Ctrl+C para parar\n")

    # Inicializa EVE
    print("Carregando EVE...")
    eve = Eve()
    print("✅ EVE carregada!\n")

    try:
        # Loop de conversação
        create_voice_loop(eve, engine="pyttsx3")  # Usa pyttsx3 por ser mais fácil de instalar

    except KeyboardInterrupt:
        print("\n\n👋 Encerrando...")
    finally:
        cleanup()
        eve.shutdown()


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO 3: USO AVANÇADO COM CONTROLE MANUAL
# ═══════════════════════════════════════════════════════════════════

def example_advanced():
    """
    Exemplo avançado com controle detalhado dos componentes.
    """
    print("=" * 60)
    print("EXEMPLO 3: Uso Avançado")
    print("=" * 60)
    print("\nEste exemplo mostra controle detalhado:")
    print("- Listener customizado")
    print("- STT com configurações específicas")
    print("- TTS com múltiplas engines")
    print("\nPressione Ctrl+C para parar\n")

    from voice import VoiceListener, SpeechToText, TextToSpeech, list_microphones

    try:
        # Lista microfones disponíveis
        print("📋 Microfones disponíveis:")
        mics = list_microphones()
        for mic in mics:
            print(f"  [{mic['index']}] {mic['name']}")
        print()

        # Inicializa componentes
        print("Inicializando componentes...")
        listener = VoiceListener()
        stt = SpeechToText(model_name="tiny")  # Modelo pequeno para teste
        tts = TextToSpeech(engine="pyttsx3")  # Engine offline
        print("✅ Componentes inicializados\n")

        # Captura áudio
        print("🎙️ Fale algo...")
        audio = listener.listen_once(timeout=30)

        if audio is not None:
            # Transcreve
            print("🔄 Transcrevendo...")
            result = stt.transcribe(audio)

            print(f"\n📝 Resultado:")
            print(f"  Texto: {result['text']}")
            print(f"  Idioma: {result['language']}")
            print(f"  Confiança: {result.get('confidence', 0):.2f}")

            # Responde
            response = f"Você disse: {result['text']}"
            print(f"\n🔊 Falando: {response}")
            tts.synthesize(response, play=True)

        else:
            print("❌ Timeout ou erro na captura")

    except KeyboardInterrupt:
        print("\n\n👋 Exemplo finalizado!")
    finally:
        if 'listener' in locals():
            listener.cleanup()


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO 4: BOT DE DISCORD
# ═══════════════════════════════════════════════════════════════════

def example_discord():
    """
    Exemplo de bot de Discord com voz.
    """
    print("=" * 60)
    print("EXEMPLO 4: Bot de Discord")
    print("=" * 60)
    print("\nEste exemplo cria um bot de Discord que:")
    print("- Entra em canais de voz")
    print("- Ouve usuários")
    print("- Transcreve automaticamente")
    print("- Responde usando TTS")
    print()

    try:
        from voice import create_voice_bot, DISCORD_AVAILABLE

        if not DISCORD_AVAILABLE:
            print("❌ discord.py não está instalado!")
            print("Instale com: pip install discord.py[voice]")
            return

        # Callback para processar transcrições
        async def on_user_message(user_id, text, ctx):
            """Processa mensagem transcrita do usuário."""
            print(f"\n📝 Usuário {user_id}: {text}")

            # Se menciona EVE, responde
            if "eve" in text.lower():
                # Inicializa EVE se necessário
                if not hasattr(on_user_message, 'eve'):
                    print("Carregando EVE...")
                    on_user_message.eve = Eve()

                # Gera resposta
                response = on_user_message.eve.generate_response(text)
                response_text = response.get("text", "")

                if response_text:
                    print(f"🤖 EVE: {response_text}")

                    # Fala no canal
                    bot = ctx.bot
                    voice_client = bot.voice_clients[0] if bot.voice_clients else None
                    if voice_client:
                        # Aqui você chamaria a função de falar
                        # (requer implementação adicional no discord_voice.py)
                        pass

        # Cria e inicia bot
        print("Iniciando bot do Discord...")
        print("\nComandos disponíveis:")
        print("  !join  - EVE entra no canal de voz")
        print("  !leave - EVE sai do canal")
        print("  !speak <texto> - EVE fala algo")
        print("  !listen - EVE começa a ouvir")
        print("  !stop - EVE para de ouvir")
        print()

        bot = create_voice_bot(on_transcription=on_user_message)
        bot.run()

    except KeyboardInterrupt:
        print("\n\n👋 Bot encerrado!")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO 5: INFORMAÇÕES DO SISTEMA
# ═══════════════════════════════════════════════════════════════════

def show_info():
    """Mostra informações sobre o módulo de voz."""
    print("=" * 60)
    print("INFORMAÇÕES DO MÓDULO DE VOZ")
    print("=" * 60)

    info = get_info()

    print(f"\n📦 Versão: {info['version']}")
    print(f"\n🎤 Componentes:")
    print(f"  Listener: {'✅' if info['components']['listener'] else '❌'}")
    print(f"  STT: {'✅' if info['components']['stt'] else '❌'}")
    print(f"  TTS: {'✅' if info['components']['tts'] else '❌'}")
    print(f"  Discord: {'✅' if info['discord_available'] else '❌'}")

    print(f"\n⚙️ Configuração:")
    print(f"  Modelo Whisper: {info['config']['whisper_model']}")
    print(f"  Sample Rate: {info['config']['sample_rate']}Hz")
    print(f"  Idioma: {info['config']['language']}")

    if 'stt_info' in info:
        print(f"\n🎙️ STT:")
        for key, value in info['stt_info'].items():
            print(f"  {key}: {value}")

    if 'tts_info' in info:
        print(f"\n🔊 TTS:")
        for key, value in info['tts_info'].items():
            print(f"  {key}: {value}")

    print()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Exemplos de uso do módulo de voz da EVE"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["simple", "eve", "advanced", "discord", "info"],
        default="simple",
        help="Modo de exemplo"
    )

    args = parser.parse_args()

    if args.mode == "simple":
        example_simple()
    elif args.mode == "eve":
        example_with_eve()
    elif args.mode == "advanced":
        example_advanced()
    elif args.mode == "discord":
        example_discord()
    elif args.mode == "info":
        show_info()


if __name__ == "__main__":
    main()
