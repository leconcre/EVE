# testar_vozes.py - TESTE FÁCIL DE VOZES EDGE TTS
"""
Script simples para testar vozes do Edge TTS.
Gera MP3 que você pode ouvir diretamente.

Uso:
    python testar_vozes.py
"""

import asyncio
from pathlib import Path

print("=" * 60)
print("TESTADOR DE VOZES - EDGE TTS")
print("=" * 60)
print()

# Verifica se edge-tts está instalado
try:
    import edge_tts
    print("✅ Edge TTS instalado")
except ImportError:
    print("❌ Edge TTS não instalado!")
    print("\nInstale com:")
    print("  pip install edge-tts")
    exit()

print()

# Texto para teste
TEXTO_TESTE = "Olá! Eu sou a EVE, sua assistente de inteligência artificial. Como posso ajudar você hoje?"

# Vozes femininas para testar (melhores para EVE)
VOZES_FEMININAS = {
    "Francisca": "pt-BR-FranciscaNeural",
    "Brenda": "pt-BR-BrendaNeural",
    "Elza": "pt-BR-ElzaNeural",
    "Leila": "pt-BR-LeilaNeural",
    "Thalita": "pt-BR-ThalitaNeural",  # Voz adicional
}

# Vozes masculinas (se quiser testar)
VOZES_MASCULINAS = {
    "Antonio": "pt-BR-AntonioNeural",
    "Donato": "pt-BR-DonatoNeural",
    "Fabio": "pt-BR-FabioNeural",
}


async def testar_voz(nome, voz_id, texto):
    """Testa uma voz e salva o áudio."""
    print(f"🔊 Gerando áudio: {nome}")
    print(f"   ID: {voz_id}")

    try:
        # Cria pasta para os áudios
        pasta = Path("voice/cache/vozes_teste")
        pasta.mkdir(parents=True, exist_ok=True)

        # Arquivo de saída
        arquivo = pasta / f"eve_{nome.lower()}.mp3"

        # Gera áudio
        communicate = edge_tts.Communicate(texto, voz_id)
        await communicate.save(str(arquivo))

        print(f"   ✅ Salvo: {arquivo}")
        print()
        return True

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        print()
        return False


async def main():
    """Função principal."""
    print("📝 Texto de teste:")
    print(f'   "{TEXTO_TESTE}"')
    print()
    print("=" * 60)
    print("GERANDO VOZES FEMININAS (recomendadas para EVE)")
    print("=" * 60)
    print()

    sucesso = []
    falhas = []

    # Testa vozes femininas
    for nome, voz_id in VOZES_FEMININAS.items():
        if await testar_voz(nome, voz_id, TEXTO_TESTE):
            sucesso.append(nome)
        else:
            falhas.append(nome)

    # Pergunta se quer testar masculinas
    print("=" * 60)
    print("VOZES MASCULINAS (opcional)")
    print("=" * 60)
    print()
    print("Quer testar vozes masculinas também? (s/N): ", end="")

    # Como é async, não dá pra usar input() direto
    # Então vamos gerar todas mesmo
    print("Gerando também...")
    print()

    for nome, voz_id in VOZES_MASCULINAS.items():
        if await testar_voz(nome, voz_id, TEXTO_TESTE):
            sucesso.append(nome)
        else:
            falhas.append(nome)

    # Resumo
    print()
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    print()

    if sucesso:
        print(f"✅ {len(sucesso)} vozes geradas com sucesso:")
        for nome in sucesso:
            arquivo = Path(f"voice/cache/vozes_teste/eve_{nome.lower()}.mp3")
            print(f"   • {nome:15} → {arquivo}")

    if falhas:
        print()
        print(f"❌ {len(falhas)} vozes falharam:")
        for nome in falhas:
            print(f"   • {nome}")

    print()
    print("=" * 60)
    print("COMO OUVIR")
    print("=" * 60)
    print()
    print("1. Abra a pasta:")
    print("   voice/cache/vozes_teste/")
    print()
    print("2. Dê duplo clique nos arquivos MP3 para ouvir")
    print()
    print("3. Escolha sua voz favorita!")
    print()
    print("=" * 60)
    print("USAR A VOZ ESCOLHIDA")
    print("=" * 60)
    print()
    print("Exemplo com voz Francisca:")
    print()
    print("  from voice import TextToSpeech")
    print('  tts = TextToSpeech(engine="edge", voice_model="pt-BR-FranciscaNeural")')
    print('  tts.synthesize("Olá!", play=True)')
    print()
    print("Ou simplesmente:")
    print()
    print("  from voice import speak")
    print('  speak("Olá!", engine="edge")  # Usa voz padrão')
    print()
    print("🎯 Depois de instalar FFmpeg, tudo funcionará automaticamente!")
    print()


if __name__ == "__main__":
    # Roda o teste
    asyncio.run(main())
