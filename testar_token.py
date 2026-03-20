"""
testar_token.py - Verifica se o token do Discord está válido

Execute: python testar_token.py
"""

import os
import sys
import io
import asyncio
from dotenv import load_dotenv

# Fix encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Carrega .env
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("❌ Token não encontrado no .env")
    sys.exit(1)

print("="*70)
print("🔍 TESTE DE TOKEN DO DISCORD")
print("="*70)
print()
print(f"Token encontrado: {TOKEN[:20]}...{TOKEN[-10:]}")
print()

# Testa token
print("📡 Testando conexão com Discord...")

try:
    import discord

    async def test_token():
        intents = discord.Intents.default()
        intents.message_content = True

        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print()
            print("="*70)
            print("✅ TOKEN VÁLIDO!")
            print("="*70)
            print(f"  Bot: {client.user.name}")
            print(f"  ID: {client.user.id}")
            print(f"  Servidores: {len(client.guilds)}")
            print()

            # Lista servidores
            if client.guilds:
                print("Servidores conectados:")
                for guild in client.guilds:
                    print(f"  - {guild.name} (ID: {guild.id})")

                    # Verifica canais de voz
                    voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
                    if voice_channels:
                        print(f"    Canais de voz: {len(voice_channels)}")
                        for vc in voice_channels[:3]:  # Mostra primeiros 3
                            print(f"      • {vc.name}")

            print()
            print("="*70)
            await client.close()

        try:
            await client.start(TOKEN)
        except discord.errors.LoginFailure:
            print()
            print("="*70)
            print("❌ TOKEN INVÁLIDO OU EXPIRADO!")
            print("="*70)
            print()
            print("Soluções:")
            print("1. Aguarde o Discord Developer Portal voltar")
            print("2. Depois regenere o token:")
            print("   https://discord.com/developers/applications")
            print("3. Atualize o .env com o novo token")
            print()
        except Exception as e:
            print(f"❌ Erro: {e}")

    asyncio.run(test_token())

except KeyboardInterrupt:
    print("\n\n👋 Teste cancelado")
except Exception as e:
    print(f"\n❌ Erro ao testar: {e}")
    import traceback
    traceback.print_exc()
