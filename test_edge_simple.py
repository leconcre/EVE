# test_edge_simple.py - TESTE SIMPLES EDGE TTS (SEM FFMPEG)
"""
Teste básico do Edge TTS que gera MP3 direto (sem precisar de FFmpeg).
"""

import asyncio
import sys
from pathlib import Path

# Adiciona voice ao path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("TESTE SIMPLES EDGE TTS (Gera MP3)")
print("=" * 60)
print()

# Verifica instalação
try:
    import edge_tts
    print("✅ edge-tts instalado")
except ImportError:
    print("❌ edge-tts NÃO instalado!")
    print("Instale com: pip install edge-tts")
    sys.exit(1)


async def test_voice(voice_name, description, text):
    """Testa uma voz específica."""
    print(f"\n🔊 Testando: {description}")
    print(f"   Voz: {voice_name}")
    print(f"   Texto: {text}")

    try:
        # Cria comunicador
        communicate = edge_tts.Communicate(text, voice_name)

        # Salva MP3
        output_file = Path(f"voice/cache/{voice_name}.mp3")
        output_file.parent.mkdir(exist_ok=True)

        await communicate.save(str(output_file))

        print(f"   ✅ Áudio gerado: {output_file}")
        print(f"   💡 Abra o arquivo para ouvir!")

        return True

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def main():
    """Função principal."""
    text = "Olá! Eu sou a EVE, sua assistente com voz neural da Microsoft."

    # Vozes para testar
    voices_to_test = [
        ("pt-BR-FranciscaNeural", "Francisca (jovem, clara)"),
        ("pt-BR-AntonioNeural", "Antonio (masculina)"),
        ("pt-BR-BrendaNeural", "Brenda (feminina)"),
    ]

    results = []

    for voice_name, description in voices_to_test:
        success = await test_voice(voice_name, description, text)
        results.append((voice_name, success))

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)

    working = [v for v, s in results if s]
    failed = [v for v, s in results if not s]

    if working:
        print(f"\n✅ {len(working)} vozes funcionando:")
        for v in working:
            print(f"   - {v}")
            print(f"     Arquivo: voice/cache/{v}.mp3")

    if failed:
        print(f"\n❌ {len(failed)} vozes com problema:")
        for v in failed:
            print(f"   - {v}")

    print("\n" + "=" * 60)
    print("PRÓXIMOS PASSOS")
    print("=" * 60)
    print()
    print("1. Ouça os arquivos MP3 gerados em: voice/cache/")
    print("2. Escolha a voz que mais gostar")
    print("3. Instale FFmpeg para integração completa:")
    print("   winget install FFmpeg")
    print()


if __name__ == "__main__":
    asyncio.run(main())
