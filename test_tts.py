# test_tts.py - TESTE DE ENGINES TTS
"""
Script para testar quais engines de TTS estão funcionando no seu sistema.
Execute: python test_tts.py
"""

import sys
from pathlib import Path

# Adiciona voice ao path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("TESTANDO ENGINES DE TTS")
print("=" * 60)
print()

# Lista de engines para testar
engines_to_test = [
    ("pyttsx3", "pyttsx3 (offline, básico)"),
    ("gtts", "gTTS (online, Google)"),
    ("piper", "Piper (offline, alta qualidade)"),
    ("coqui", "Coqui TTS (offline, melhor qualidade)"),
]

results = []

for engine_name, description in engines_to_test:
    print(f"Testando {description}...")

    try:
        from voice import TextToSpeech

        # Tenta inicializar a engine
        tts = TextToSpeech(engine=engine_name)

        # Tenta sintetizar (sem reproduzir)
        audio = tts.synthesize("Teste", play=False)

        if audio is not None:
            print(f"  ✅ {engine_name.upper()} FUNCIONANDO!")
            results.append((engine_name, True, ""))
        else:
            print(f"  ⚠️ {engine_name.upper()} inicializou mas não sintetizou")
            results.append((engine_name, False, "Falha na síntese"))

    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ {engine_name.upper()} FALHOU: {error_msg[:60]}")
        results.append((engine_name, False, error_msg))

    print()

# Resumo
print("=" * 60)
print("RESUMO")
print("=" * 60)
print()

working_engines = [r for r in results if r[1]]
failed_engines = [r for r in results if not r[1]]

if working_engines:
    print("✅ Engines funcionando:")
    for engine, _, _ in working_engines:
        print(f"   - {engine}")
    print()
else:
    print("❌ Nenhuma engine está funcionando!")
    print()

if failed_engines:
    print("❌ Engines com problemas:")
    for engine, _, error in failed_engines:
        print(f"   - {engine}")
        if "not installed" in error.lower() or "no module" in error.lower():
            print(f"     → Não instalado. Instale com: pip install {engine}")
        elif "piper" in engine and "not found" in error.lower():
            print(f"     → Instale Piper: winget install rhasspy.piper")
        else:
            print(f"     → Erro: {error[:100]}")
    print()

# Recomendação
print("=" * 60)
print("RECOMENDAÇÃO")
print("=" * 60)
print()

if working_engines:
    recommended = working_engines[0][0]
    print(f"Use esta engine para começar: {recommended}")
    print()
    print("Exemplo:")
    print(f'  from voice import speak')
    print(f'  speak("Olá, eu sou a EVE!", engine="{recommended}")')
else:
    print("Nenhuma engine funcionando. Siga estas etapas:")
    print()
    print("1. Instale pyttsx3 (mais fácil):")
    print("   pip install pyttsx3")
    print()
    print("2. Teste novamente:")
    print("   python test_tts.py")
    print()
    print("Para mais ajuda, veja: voice/INSTALL_TTS.md")

print()
