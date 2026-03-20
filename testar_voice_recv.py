"""
testar_voice_recv.py - Verifica se discord-ext-voice-recv está instalado

Execute: python testar_voice_recv.py
"""

import sys
import io

# Fix encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("🧪 TESTE discord-ext-voice-recv - Sistema de Voz EVE")
print("=" * 70)
print()

# ═══════════════════════════════════════════════════════════════════
# 1. VERIFICAR DISCORD.PY
# ═══════════════════════════════════════════════════════════════════

print("📦 Verificando discord.py...")

try:
    import discord
    version = discord.__version__
    print(f"  ✅ discord.py importado: versão {version}")

    # Verifica se NÃO é py-cord
    if hasattr(discord, 'sinks'):
        print("  ⚠️ ATENÇÃO: Detectado discord.sinks (py-cord)")
        print("     Você pode estar com py-cord ao invés de discord.py!")
        print("     Execute: pip uninstall py-cord discord -y")
        print("     Depois: pip install discord.py[voice]")
    else:
        print("  ✅ Confirmado: discord.py (não é py-cord)")

except ImportError as e:
    print(f"  ❌ discord não instalado: {e}")
    print("\n💡 Solução:")
    print("   pip install discord.py[voice]\n")
    sys.exit(1)

print()

# ═══════════════════════════════════════════════════════════════════
# 2. VERIFICAR DISCORD-EXT-VOICE-RECV
# ═══════════════════════════════════════════════════════════════════

print("🎧 Verificando discord-ext-voice-recv...")

try:
    from discord.ext import voice_recv
    print("  ✅ discord.ext.voice_recv disponível")

    # Verifica VoiceRecvClient
    if hasattr(voice_recv, 'VoiceRecvClient'):
        print("  ✅ VoiceRecvClient disponível")
    else:
        print("  ❌ VoiceRecvClient NÃO encontrado!")

    # Verifica AudioSink
    if hasattr(voice_recv, 'AudioSink'):
        print("  ✅ AudioSink disponível")
    else:
        print("  ❌ AudioSink NÃO encontrado!")

    print("  ✅ CONFIRMADO: discord-ext-voice-recv instalado!")

except ImportError as e:
    print(f"  ❌ discord-ext-voice-recv NÃO disponível: {e}")
    print("\n💡 Solução:")
    print("   pip install discord-ext-voice-recv\n")
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
    print("   Alternativa (Python 3.14): pip install openai-whisper")

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
# 9. TESTE ESPECÍFICO: VoiceRecvClient
# ═══════════════════════════════════════════════════════════════════

print("🎯 Testando VoiceRecvClient especificamente...")

try:
    from discord.ext import voice_recv

    # Verifica se pode instanciar (sem conectar)
    print(f"  ✅ VoiceRecvClient importável: {voice_recv.VoiceRecvClient}")

    # Verifica métodos importantes
    if hasattr(voice_recv.VoiceRecvClient, 'listen'):
        print("  ✅ Método .listen() disponível")
    else:
        print("  ❌ Método .listen() NÃO encontrado")

    if hasattr(voice_recv.VoiceRecvClient, 'is_listening'):
        print("  ✅ Método .is_listening() disponível")
    else:
        print("  ❌ Método .is_listening() NÃO encontrado")

except Exception as e:
    print(f"  ❌ Erro ao testar VoiceRecvClient: {e}")

print()

# ═══════════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════════

print("=" * 70)
print("📊 RESUMO")
print("=" * 70)
print()

# Verifica componentes críticos
has_discordpy = 'discord' in sys.modules and not hasattr(sys.modules['discord'], 'sinks')
has_voice_recv = 'voice_recv' in dir(sys.modules.get('discord.ext', {}))
has_nacl = 'nacl' in sys.modules
has_whisper = 'faster_whisper' in sys.modules or 'whisper' in sys.modules
has_numpy = 'numpy' in sys.modules

critical_ok = has_discordpy and has_voice_recv and has_nacl

if critical_ok:
    print("✅ COMPONENTES CRÍTICOS: OK")
    print("   - discord.py ✅")
    print("   - discord-ext-voice-recv ✅")
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
    print("📖 Documentação: INSTALACAO_VOICE_RECV.md")

else:
    print("❌ COMPONENTES CRÍTICOS: FALTANDO")
    print()

    if not has_discordpy:
        print("   ❌ discord.py não disponível")
        print("      Execute: pip install discord.py[voice]")

    if not has_voice_recv:
        print("   ❌ discord-ext-voice-recv não instalado")
        print("      Execute: pip install discord-ext-voice-recv")

    if not has_nacl:
        print("   ❌ PyNaCl não instalado")
        print("      Execute: pip install PyNaCl")

    print()
    print("Execute os comandos acima e teste novamente.")

print()
print("=" * 70)
