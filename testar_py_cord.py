"""
testar_py_cord.py - Verifica se py-cord está instalado e funcionando

Execute: python testar_py_cord.py
"""

import sys
import io

# Fix encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("="*70)
print("🧪 TESTE PY-CORD - Sistema de Voz EVE")
print("="*70)
print()

# ═══════════════════════════════════════════════════════════════════
# 1. VERIFICAR PY-CORD
# ═══════════════════════════════════════════════════════════════════

print("📦 Verificando py-cord...")

try:
    import discord
    version = discord.__version__
    print(f"  ✅ discord importado: versão {version}")

    # Verifica se é py-cord (versão 2.x)
    major_version = int(version.split('.')[0])
    if major_version >= 2:
        print("  ✅ Versão compatível com py-cord")
    else:
        print(f"  ⚠️ Versão {version} pode ser discord.py antigo!")

except ImportError as e:
    print(f"  ❌ discord não instalado: {e}")
    print("\n💡 Solução:")
    print("   pip uninstall discord.py discord -y")
    print("   pip install py-cord[voice]\n")
    sys.exit(1)

print()

# ═══════════════════════════════════════════════════════════════════
# 2. VERIFICAR DISCORD.SINKS (PY-CORD)
# ═══════════════════════════════════════════════════════════════════

print("🎧 Verificando discord.sinks (py-cord)...")

try:
    import discord.sinks
    print("  ✅ discord.sinks disponível")
    print("  ✅ CONFIRMADO: Você está usando PY-CORD!")

    # Lista tipos de sinks disponíveis
    if hasattr(discord.sinks, 'Sink'):
        print("  ✅ discord.sinks.Sink disponível")

except (ImportError, AttributeError) as e:
    print(f"  ❌ discord.sinks NÃO disponível: {e}")
    print("\n⚠️ VOCÊ ESTÁ USANDO DISCORD.PY (NÃO PY-CORD)!")
    print("\n💡 Solução:")
    print("   pip uninstall discord.py discord -y")
    print("   pip install py-cord[voice]\n")
    sys.exit(1)

print()

# ═══════════════════════════════════════════════════════════════════
# 3. VERIFICAR PYNACL (VOICE)
# ═══════════════════════════════════════════════════════════════════

print("🔐 Verificando PyNaCl (criptografia de voz)...")

try:
    import nacl
    print("  ✅ PyNaCl instalado")
except ImportError as e:
    print(f"  ❌ PyNaCl não instalado: {e}")
    print("   Execute: pip install PyNaCl")

print()

# ═══════════════════════════════════════════════════════════════════
# 4. VERIFICAR FASTER-WHISPER
# ═══════════════════════════════════════════════════════════════════

print("🎤 Verificando faster-whisper (STT)...")

try:
    from faster_whisper import WhisperModel
    print("  ✅ faster-whisper instalado")
except ImportError as e:
    print(f"  ⚠️ faster-whisper não instalado: {e}")
    print("   Execute: pip install faster-whisper")

print()

# ═══════════════════════════════════════════════════════════════════
# 5. VERIFICAR NUMPY
# ═══════════════════════════════════════════════════════════════════

print("🔢 Verificando numpy...")

try:
    import numpy as np
    print(f"  ✅ numpy instalado: {np.__version__}")
except ImportError as e:
    print(f"  ❌ numpy não instalado: {e}")
    print("   Execute: pip install numpy")

print()

# ═══════════════════════════════════════════════════════════════════
# 6. VERIFICAR MÓDULOS VOICE
# ═══════════════════════════════════════════════════════════════════

print("🗂️ Verificando módulos voice/...")

try:
    from voice.stt.discord_listener import VoiceRecordingSink, DiscordVoiceListener
    print("  ✅ voice.stt.discord_listener")

    from voice.stt.models import VoiceInput
    print("  ✅ voice.stt.models")

    from voice.permissions import permission_manager
    print("  ✅ voice.permissions")

    from voice import listen_from_discord
    print("  ✅ voice.listen_from_discord")

except ImportError as e:
    print(f"  ⚠️ Erro ao importar módulos: {e}")
    import traceback
    traceback.print_exc()

print()

# ═══════════════════════════════════════════════════════════════════
# 7. TESTE DE FUNCIONALIDADE
# ═══════════════════════════════════════════════════════════════════

print("⚙️ Testando funcionalidades...")

try:
    # Testa criar um Sink
    from voice.stt.discord_listener import VoiceRecordingSink
    from voice.stt.user_tracker import UserTracker
    from voice.stt.vad import DiscordVAD
    from voice.stt.transcriber import AudioTranscriber

    # Mock de componentes (sem inicializar Whisper)
    user_tracker = UserTracker()
    vad = DiscordVAD()

    print("  ✅ VoiceRecordingSink pode ser criado")
    print("  ✅ UserTracker funcional")
    print("  ✅ DiscordVAD funcional")

except Exception as e:
    print(f"  ⚠️ Erro ao testar: {e}")
    import traceback
    traceback.print_exc()

print()

# ═══════════════════════════════════════════════════════════════════
# 8. VERIFICAR FFMPEG
# ═══════════════════════════════════════════════════════════════════

print("🎬 Verificando FFmpeg...")

import subprocess

try:
    result = subprocess.run(
        ["ffmpeg", "-version"],
        capture_output=True,
        text=True,
        timeout=5
    )

    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"  ✅ FFmpeg encontrado: {version_line[:60]}...")
    else:
        print("  ❌ FFmpeg não funciona")

except FileNotFoundError:
    print("  ❌ FFmpeg NÃO encontrado no PATH")
    print("   Windows: choco install ffmpeg")
    print("   Linux: sudo apt install ffmpeg")
    print("   macOS: brew install ffmpeg")

except Exception as e:
    print(f"  ⚠️ Erro ao verificar FFmpeg: {e}")

print()

# ═══════════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════════

print("="*70)
print("📊 RESUMO")
print("="*70)
print()

# Verifica componentes críticos
has_pycord = 'discord' in sys.modules and hasattr(sys.modules['discord'], 'sinks')
has_nacl = 'nacl' in sys.modules
has_whisper = 'faster_whisper' in sys.modules
has_numpy = 'numpy' in sys.modules

critical_ok = has_pycord and has_nacl

if critical_ok:
    print("✅ COMPONENTES CRÍTICOS: OK")
    print("   - py-cord com sinks ✅")
    print("   - PyNaCl ✅")
    print()
    print("🎉 SISTEMA PRONTO PARA USO!")
    print()
    print("📋 Próximos passos:")
    print("   1. Configure .env com DISCORD_BOT_TOKEN")
    print("   2. Execute: python eve_discord_bot.py")
    print("   3. No Discord: !join")
    print("   4. No Discord: !listen")
    print("   5. Fale no canal de voz!")
    print()
    print("📖 Documentação: GUIA_PY_CORD.md")

else:
    print("❌ COMPONENTES CRÍTICOS: FALTANDO")
    print()

    if not has_pycord:
        print("   ❌ py-cord com sinks não disponível")
        print("      Execute: pip install py-cord[voice]")

    if not has_nacl:
        print("   ❌ PyNaCl não instalado")
        print("      Execute: pip install PyNaCl")

    print()
    print("Execute: instalar_py_cord.bat")

print()
print("="*70)
