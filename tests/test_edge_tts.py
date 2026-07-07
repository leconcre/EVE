# test_edge_tts.py - TESTE RÁPIDO DO EDGE TTS
"""
Script para testar Edge TTS com diferentes vozes brasileiras.

Instalação:
    pip install edge-tts

Uso:
    python test_edge_tts.py
"""

import sys
from pathlib import Path

# Adiciona voice ao path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("TESTE DO EDGE TTS (Microsoft)")
print("=" * 60)
print()

# Verifica instalação
try:
    import edge_tts
    print("✅ edge-tts está instalado")
except ImportError:
    print("❌ edge-tts NÃO está instalado!")
    print()
    print("Instale com:")
    print("  pip install edge-tts")
    print()
    sys.exit(1)

# Importa engine
try:
    from voice.edge_tts_engine import EdgeTTSEngine, list_brazilian_voices
    print("✅ EdgeTTSEngine carregado")
    print()
except Exception as e:
    print(f"❌ Erro ao carregar EdgeTTSEngine: {e}")
    sys.exit(1)

# Lista vozes disponíveis
print("=" * 60)
print("VOZES DISPONÍVEIS")
print("=" * 60)
print()
list_brazilian_voices()
print()

# Testa síntese
print("=" * 60)
print("TESTANDO SÍNTESE")
print("=" * 60)
print()

# Texto de teste
test_text = "Olá! Eu sou a EVE, sua assistente com voz neural da Microsoft."

# Vozes para testar (femininas recomendadas para EVE)
voices_to_test = [
    ("francisca", "Francisca (jovem, clara)"),
    ("yara", "Yara (natural)"),
    ("leticia", "Letícia (suave)"),
]

print("Testando vozes femininas (recomendadas para EVE):")
print()

for voice_name, description in voices_to_test:
    print(f"🔊 Testando: {description}")
    print(f"   Texto: {test_text}")

    try:
        # Cria engine
        engine = EdgeTTSEngine(voice=voice_name)

        # Sintetiza
        audio_file = engine.synthesize(test_text)

        print(f"   ✅ Áudio gerado: {audio_file}")
        print(f"   💡 Para ouvir, abra: {audio_file}")
        print()

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        print()

# Teste com a API simplificada
print("=" * 60)
print("TESTE COM API SIMPLIFICADA")
print("=" * 60)
print()

try:
    from voice import speak

    print("🔊 Teste com voice.speak() usando Edge TTS...")
    speak("Teste de voz usando a API simplificada.", engine="edge", play=False)
    print("✅ Sucesso!")
    print()

except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
    print()

# Resumo
print("=" * 60)
print("RESUMO")
print("=" * 60)
print()
print("✅ Edge TTS está funcionando!")
print()
print("📝 Como usar:")
print()
print("1. Uso simples:")
print('   from voice import speak')
print('   speak("Olá!", engine="edge")')
print()
print("2. Escolher voz específica:")
print('   from voice import TextToSpeech')
print('   tts = TextToSpeech(engine="edge", voice_model="yara")')
print('   tts.synthesize("Olá!", play=True)')
print()
print("3. Integrar com EVE:")
print('   from voice import create_voice_loop')
print('   from core.eve import Eve')
print('   eve = Eve()')
print('   # Modifique create_voice_loop para usar engine="edge"')
print()
print("🎯 Vozes recomendadas para EVE:")
print("   - francisca (clara, jovem)")
print("   - yara (natural, equilibrada)")
print("   - leticia (suave, agradável)")
print()
