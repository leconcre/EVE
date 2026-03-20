# eve_com_voz.py - EVE COM VOZ DA FRANCISCA
"""
Exemplo de uso da EVE com voz Edge TTS (Francisca).

Uso:
    python eve_com_voz.py
"""

import sys
from pathlib import Path

# Adiciona ao path se necessário
sys.path.insert(0, str(Path(__file__).parent))

from core.eve import Eve
from voice import TextToSpeech

print("=" * 60)
print("EVE - ASSISTENTE COM VOZ")
print("Voz: Francisca (Edge TTS)")
print("=" * 60)
print()

# Inicializa EVE
print("Carregando EVE...")
eve = Eve()
print("✅ EVE carregada!")
print()

# Configura TTS com voz Francisca
print("Configurando voz (Francisca)...")
tts = TextToSpeech(engine="edge", voice_model="pt-BR-FranciscaNeural")
print("✅ Voz configurada!")
print()

print("=" * 60)
print("MODO DE CONVERSA")
print("=" * 60)
print()
print("💡 Dica: Por enquanto, digite suas perguntas no teclado.")
print("   (Depois de instalar PyAudio, poderá usar voz para perguntar)")
print()
print("📝 Digite 'sair' para encerrar")
print()

# Loop de conversa
contador = 0

while True:
    # Recebe pergunta (por enquanto via teclado)
    print("-" * 60)
    pergunta = input("👤 Você: ").strip()

    if not pergunta:
        continue

    # Comandos especiais
    if pergunta.lower() in ['sair', 'exit', 'quit', 'tchau']:
        print()
        print("👋 Encerrando EVE...")

        # Despedida falada
        despedida = "Até logo! Foi um prazer conversar com você."
        print(f"🤖 EVE: {despedida}")

        arquivo_despedida = f"eve_despedida.mp3"
        tts.synthesize(despedida, save_to=arquivo_despedida, play=False)
        print(f"💾 Áudio salvo: {arquivo_despedida}")

        eve.shutdown()
        break

    # Processa com EVE
    print()
    print("🤖 EVE: ", end="", flush=True)

    resposta = eve.generate_response(pergunta)
    texto_eve = resposta.get('text', '')

    if not texto_eve:
        texto_eve = "Desculpe, não consegui processar sua pergunta."

    # Mostra resposta
    print(texto_eve)

    # Gera áudio da resposta
    contador += 1
    arquivo_audio = f"eve_resposta_{contador}.mp3"

    print()
    print(f"🔊 Gerando áudio ({arquivo_audio})...")

    try:
        tts.synthesize(texto_eve, save_to=arquivo_audio, play=False)
        print(f"✅ Áudio salvo: {arquivo_audio}")
        print(f"💡 Abra o arquivo para ouvir a resposta!")
    except Exception as e:
        print(f"❌ Erro ao gerar áudio: {e}")

    print()

print()
print("=" * 60)
print("SESSÃO ENCERRADA")
print("=" * 60)
print()
print(f"📂 {contador} áudios gerados nesta sessão")
print()
print("💡 Próximos passos:")
print("   1. Instale FFmpeg: winget install FFmpeg")
print("   2. Instale PyAudio para usar voz nas perguntas")
print("   3. Áudio tocará automaticamente!")
print()
