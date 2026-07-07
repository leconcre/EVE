"""
exemplo_voice_listening.py - Exemplo de Uso do Sistema de Escuta de Voz

Demonstra como usar o sistema de escuta programaticamente.
"""

import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Importa sistema de escuta
from voice import listen_from_discord, VoiceInput, permission_manager

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("exemplo_voice")

# Configura intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# Cria bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Controle de escuta
listening_active = False


# ═══════════════════════════════════════════════════════════════════
# CALLBACK: PROCESSA VOZ
# ═══════════════════════════════════════════════════════════════════

async def processar_voz(voice_input: VoiceInput):
    """
    Callback chamado quando alguém fala no canal.

    Este é o coração do sistema - aqui você processa o que foi dito.

    Args:
        voice_input: Dados completos da entrada de voz
    """
    # ─────────────────────────────────────────────────────────────
    # 1. LOG DA ENTRADA
    # ─────────────────────────────────────────────────────────────

    # Monta tags de identificação
    tags = []
    if voice_input.is_creator:
        tags.append("CREATOR")
    if voice_input.is_admin:
        tags.append("ADMIN")

    tag_str = f" [{'/'.join(tags)}]" if tags else ""

    logger.info(f"🎤 {voice_input.username}{tag_str}: {voice_input.text}")

    # ─────────────────────────────────────────────────────────────
    # 2. INFORMAÇÕES DETALHADAS
    # ─────────────────────────────────────────────────────────────

    print("\n" + "="*70)
    print(f"📊 DETALHES DA ENTRADA DE VOZ")
    print("="*70)
    print(f"  Usuário:      {voice_input.username} (ID: {voice_input.user_id})")
    print(f"  Texto:        {voice_input.text}")
    print(f"  Confiança:    {voice_input.confidence:.2%}")
    print(f"  Duração:      {voice_input.audio_duration:.2f}s")
    print(f"  Idioma:       {voice_input.language}")
    print(f"  Timestamp:    {voice_input.timestamp.strftime('%H:%M:%S')}")
    print(f"  É criador?    {'✅ SIM' if voice_input.is_creator else '❌ NÃO'}")
    print(f"  É admin?      {'✅ SIM' if voice_input.is_admin else '❌ NÃO'}")
    print(f"  Roles:        {', '.join(voice_input.roles) if voice_input.roles else 'Nenhuma'}")
    print("="*70 + "\n")

    # ─────────────────────────────────────────────────────────────
    # 3. PROCESSAMENTO POR PERMISSÃO
    # ─────────────────────────────────────────────────────────────

    texto_lower = voice_input.text.lower()

    # Comandos exclusivos do criador
    if voice_input.is_creator:
        if "desligar bot" in texto_lower:
            logger.warning("🔴 Comando de desligamento recebido do criador!")
            # await bot.close()
            print("⚠️ [SIMULADO] Bot seria desligado aqui")

        elif "status" in texto_lower:
            print(f"✅ Bot online | Usuários rastreados: {len(bot.users)}")

    # Comandos de admin
    elif voice_input.is_admin:
        if "limpar" in texto_lower:
            print("🧹 [SIMULADO] Limparia o canal de texto")

    # Comandos gerais (todos os usuários)
    if "olá" in texto_lower or "oi" in texto_lower:
        print(f"👋 {voice_input.username} disse olá!")

    elif "hora" in texto_lower:
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M")
        print(f"🕐 São {hora}")

    elif "ajuda" in texto_lower:
        print("💡 Comandos disponíveis:")
        print("   - Olá/Oi: Saudação")
        print("   - Que horas são?: Mostra hora atual")
        print("   - Ajuda: Mostra esta mensagem")
        if voice_input.is_creator:
            print("   [CREATOR] - Desligar bot: Desliga o bot")
            print("   [CREATOR] - Status: Mostra status do bot")

    # ─────────────────────────────────────────────────────────────
    # 4. VERIFICAÇÃO DE CONFIANÇA
    # ─────────────────────────────────────────────────────────────

    if voice_input.confidence < 0.5:
        print(f"⚠️ AVISO: Transcrição com baixa confiança ({voice_input.confidence:.2%})")
        print(f"   Pode haver erros no texto: '{voice_input.text}'")

    # ─────────────────────────────────────────────────────────────
    # 5. AQUI VOCÊ INTEGRARIA COM SUA IA
    # ─────────────────────────────────────────────────────────────

    # Exemplo: integração com EVE
    # from core.eve import Eve
    # eve = Eve()
    # response = eve.generate_response(voice_input.text)
    # print(f"🤖 EVE: {response.get('text')}")


# ═══════════════════════════════════════════════════════════════════
# EVENTOS DO BOT
# ═══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    """Executado quando bot está pronto."""
    print("\n" + "="*70)
    print("🤖 BOT DE EXEMPLO - SISTEMA DE ESCUTA DE VOZ")
    print("="*70)
    print(f"  Conectado como:  {bot.user.name} (ID: {bot.user.id})")
    print(f"  Servidores:      {len(bot.guilds)}")
    print("="*70)
    print("\n📋 Comandos disponíveis:")
    print("   !join         - Entrar no canal de voz")
    print("   !listen       - Iniciar escuta")
    print("   !stop_listen  - Parar escuta")
    print("   !leave        - Sair do canal\n")
    print("💡 Use !listen para ativar o sistema de escuta de voz!\n")

    # Configura o criador (substitua pelo seu username)
    permission_manager.creator_username = "Leconcre"


# ═══════════════════════════════════════════════════════════════════
# COMANDOS
# ═══════════════════════════════════════════════════════════════════

@bot.command(name="join", help="Bot entra no canal de voz")
async def join(ctx):
    """Entra no canal de voz do usuário."""
    if not ctx.author.voice:
        await ctx.send("❌ Você precisa estar em um canal de voz!")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
        await ctx.send(f"✅ Movido para: {channel.name}")
    else:
        await channel.connect()
        await ctx.send(f"✅ Conectado ao canal: {channel.name}")

    logger.info(f"Conectado ao canal: {channel.name}")


@bot.command(name="listen", help="Inicia sistema de escuta")
async def start_listen(ctx):
    """Inicia escuta de voz."""
    global listening_active

    if listening_active:
        await ctx.send("⚠️ Já estou escutando!")
        return

    if not ctx.voice_client:
        if not ctx.author.voice:
            await ctx.send("❌ Entre em um canal de voz primeiro!")
            return
        await ctx.author.voice.channel.connect()

    try:
        await ctx.send("🎧 Iniciando sistema de escuta... (carregando modelo Whisper)")

        # ★ AQUI É ONDE A MÁGICA ACONTECE ★
        await listen_from_discord(
            ctx.voice_client,
            on_transcription=processar_voz,  # ← Seu callback
            model_size="small"  # tiny, small, medium, large-v3
        )

        listening_active = True

        await ctx.send(
            "✅ **Sistema de escuta ATIVADO!**\n\n"
            "🎤 Fale normalmente no canal de voz\n"
            "💬 Suas falas serão transcritas e processadas\n"
            "📊 Veja os logs no console\n\n"
            "⏹️ Use `!stop_listen` para parar"
        )

        logger.info("✅ Sistema de escuta ativado com sucesso")

    except Exception as e:
        logger.error(f"Erro ao iniciar escuta: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name="stop_listen", help="Para sistema de escuta")
async def stop_listen_cmd(ctx):
    """Para a escuta."""
    global listening_active

    if not listening_active:
        await ctx.send("⚠️ Não estou escutando no momento!")
        return

    try:
        from voice import stop_listening
        await stop_listening()
        listening_active = False

        await ctx.send("⏹️ Sistema de escuta desativado")
        logger.info("Sistema de escuta desativado")

    except Exception as e:
        logger.error(f"Erro ao parar escuta: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name="leave", help="Bot sai do canal de voz")
async def leave(ctx):
    """Sai do canal de voz."""
    global listening_active

    if listening_active:
        from voice import stop_listening
        await stop_listening()
        listening_active = False

    if not ctx.voice_client:
        await ctx.send("❌ Não estou em nenhum canal!")
        return

    await ctx.voice_client.disconnect()
    await ctx.send("👋 Saindo do canal de voz...")
    logger.info("Desconectado do canal de voz")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    if not TOKEN:
        print("❌ ERRO: DISCORD_BOT_TOKEN não encontrado no .env")
        print("\n📝 Configure o arquivo .env:")
        print("   DISCORD_BOT_TOKEN=seu_token_aqui\n")
        exit(1)

    print("\n🚀 Iniciando bot de exemplo...")
    print("📡 Conectando ao Discord...\n")

    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n\n👋 Bot encerrado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro ao executar bot: {e}")
        import traceback
        traceback.print_exc()
