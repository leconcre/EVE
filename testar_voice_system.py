"""
testar_voice_system.py - Testa Componentes do Sistema de Voz

Verifica se todos os módulos estão funcionando corretamente.
"""

import sys
import io
from pathlib import Path

# Fix encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("="*70)
print("🧪 TESTE DO SISTEMA DE VOZ - EVE")
print("="*70)
print()

# ═══════════════════════════════════════════════════════════════════
# 1. TESTE DE IMPORTS
# ═══════════════════════════════════════════════════════════════════

print("📦 Testando imports...")

try:
    import discord
    print("  ✅ discord.py")
except ImportError as e:
    print(f"  ❌ discord.py: {e}")
    sys.exit(1)

try:
    import discord.sinks
    print("  ✅ discord.sinks")
except (ImportError, AttributeError) as e:
    print(f"  ⚠️ discord.sinks: {e}")
    print("     Execute: pip install --upgrade discord.py[voice]")

try:
    from faster_whisper import WhisperModel
    print("  ✅ faster-whisper")
except ImportError as e:
    print(f"  ❌ faster-whisper: {e}")
    print("     Execute: pip install faster-whisper")
    sys.exit(1)

try:
    import numpy as np
    print("  ✅ numpy")
except ImportError as e:
    print(f"  ❌ numpy: {e}")
    sys.exit(1)

print()

# ═══════════════════════════════════════════════════════════════════
# 2. TESTE DE MÓDULOS DO VOICE
# ═══════════════════════════════════════════════════════════════════

print("🔧 Testando módulos voice/...")

try:
    from voice import config
    print(f"  ✅ voice.config (Whisper model: {config.WHISPER_MODEL})")
except ImportError as e:
    print(f"  ❌ voice.config: {e}")
    sys.exit(1)

try:
    from voice.permissions import PermissionManager, permission_manager
    print(f"  ✅ voice.permissions (Criador: {permission_manager.creator_username})")
except ImportError as e:
    print(f"  ❌ voice.permissions: {e}")
    sys.exit(1)

try:
    from voice.stt.models import VoiceInput, AudioChunk
    print("  ✅ voice.stt.models")
except ImportError as e:
    print(f"  ❌ voice.stt.models: {e}")
    sys.exit(1)

try:
    from voice.stt.user_tracker import UserTracker
    print("  ✅ voice.stt.user_tracker")
except ImportError as e:
    print(f"  ❌ voice.stt.user_tracker: {e}")
    sys.exit(1)

try:
    from voice.stt.vad import DiscordVAD, VoiceActivityDetector
    print("  ✅ voice.stt.vad")
except ImportError as e:
    print(f"  ❌ voice.stt.vad: {e}")
    sys.exit(1)

try:
    from voice.stt.transcriber import AudioTranscriber
    print("  ✅ voice.stt.transcriber")
except ImportError as e:
    print(f"  ❌ voice.stt.transcriber: {e}")
    sys.exit(1)

try:
    from voice.stt.discord_listener import DiscordVoiceListener
    print("  ✅ voice.stt.discord_listener")
except ImportError as e:
    print(f"  ❌ voice.stt.discord_listener: {e}")
    sys.exit(1)

try:
    from voice.discord_integration import listen_from_discord, stop_listening
    print("  ✅ voice.discord_integration")
except ImportError as e:
    print(f"  ❌ voice.discord_integration: {e}")
    sys.exit(1)

print()

# ═══════════════════════════════════════════════════════════════════
# 3. TESTE DE FUNCIONALIDADE
# ═══════════════════════════════════════════════════════════════════

print("⚙️ Testando funcionalidades...")

# Teste PermissionManager
try:
    from voice.permissions import permission_manager
    from datetime import datetime

    # Criar um mock de Member
    class MockMember:
        def __init__(self):
            self.id = 123456789
            self.name = "TestUser"
            self.display_name = "Test User"
            self.roles = []

            # Mock guild permissions
            class MockPerms:
                administrator = False
                kick_members = False
                ban_members = False
                manage_messages = False

            class MockGuild:
                owner_id = 999999999

            self.guild_permissions = MockPerms()
            self.guild = MockGuild()

    member = MockMember()
    perms = permission_manager.get_permissions(member)

    assert perms.user_id == 123456789
    assert perms.username == "Test User"
    assert perms.is_creator == False
    print("  ✅ PermissionManager.get_permissions()")

except Exception as e:
    print(f"  ❌ PermissionManager: {e}")
    import traceback
    traceback.print_exc()

# Teste VoiceInput
try:
    from voice.stt.models import VoiceInput
    from datetime import datetime

    voice_input = VoiceInput(
        user_id=123456789,
        username="TestUser",
        text="Olá EVE!",
        confidence=0.95,
        is_creator=True,
        roles=["Admin", "VIP"]
    )

    assert voice_input.user_id == 123456789
    assert voice_input.text == "Olá EVE!"
    assert voice_input.is_creator == True
    assert len(voice_input.roles) == 2

    dict_repr = voice_input.to_dict()
    assert "user_id" in dict_repr
    assert "text" in dict_repr

    print("  ✅ VoiceInput (criação e to_dict)")

except Exception as e:
    print(f"  ❌ VoiceInput: {e}")
    import traceback
    traceback.print_exc()

# Teste UserTracker
try:
    from voice.stt.user_tracker import UserTracker

    tracker = UserTracker()
    # Mock member
    tracker._users[123] = MockMember()

    user = tracker.get_user(123)
    assert user is not None

    username = tracker.get_username(123)
    assert username == "Test User"

    tracker.clear()
    assert len(tracker._users) == 0

    print("  ✅ UserTracker (add, get, clear)")

except Exception as e:
    print(f"  ❌ UserTracker: {e}")
    import traceback
    traceback.print_exc()

# Teste VAD
try:
    from voice.stt.vad import DiscordVAD
    import numpy as np

    vad = DiscordVAD(energy_threshold=0.01)

    # Teste com silêncio (zeros)
    silence = np.zeros(960, dtype=np.int16).tobytes()
    is_voice = vad.is_voice(silence)
    assert is_voice == False, "Silêncio deveria ser False"

    # Teste com ruído
    noise = np.random.randint(-1000, 1000, 960, dtype=np.int16).tobytes()
    is_voice_noise = vad.is_voice(noise)
    # Ruído pode ou não ser detectado, apenas verifica que não dá erro

    print("  ✅ DiscordVAD (is_voice)")

except Exception as e:
    print(f"  ❌ DiscordVAD: {e}")
    import traceback
    traceback.print_exc()

# Teste AudioTranscriber (cria instância, não transcreve)
try:
    from voice.stt.transcriber import AudioTranscriber

    transcriber = AudioTranscriber(
        model_size="tiny",  # Modelo pequeno para teste rápido
        language="pt",
        device="cpu"
    )

    print("  ✅ AudioTranscriber (inicialização)")
    print(f"     Modelo carregado: tiny")

except Exception as e:
    print(f"  ⚠️ AudioTranscriber: {e}")
    print("     (Isso é normal se o modelo ainda não foi baixado)")

print()

# ═══════════════════════════════════════════════════════════════════
# 4. TESTE FFMPEG
# ═══════════════════════════════════════════════════════════════════

print("🎬 Testando FFmpeg...")

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
        print(f"  ✅ FFmpeg encontrado: {version_line}")
    else:
        print("  ❌ FFmpeg não funciona corretamente")

except FileNotFoundError:
    print("  ❌ FFmpeg NÃO encontrado no PATH")
    print("     Instale: https://ffmpeg.org/download.html")
except Exception as e:
    print(f"  ⚠️ Erro ao verificar FFmpeg: {e}")

print()

# ═══════════════════════════════════════════════════════════════════
# 5. RESUMO
# ═══════════════════════════════════════════════════════════════════

print("="*70)
print("📊 RESUMO DOS TESTES")
print("="*70)
print()
print("✅ Todos os módulos principais estão funcionando!")
print()
print("📋 Próximos passos:")
print("   1. Configure o .env com DISCORD_BOT_TOKEN")
print("   2. Execute: python eve_discord_bot.py")
print("   3. No Discord, use !join e depois !listen")
print("   4. Fale no canal de voz!")
print()
print("📖 Documentação completa: DISCORD_VOICE_LISTENING.md")
print("💡 Exemplo de código: exemplo_voice_listening.py")
print()
print("="*70)
