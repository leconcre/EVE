# 🚀 Guia de Instalação Rápida - Sistema de Voz EVE

## ⚡ Instalação em 5 Minutos

### 1. Instalar FFmpeg

**Windows:**
```powershell
# Opção 1: Chocolatey (recomendado)
choco install ffmpeg

# Opção 2: Manual
# 1. Baixe: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
# 2. Extraia para C:\ffmpeg
# 3. Adicione C:\ffmpeg\bin ao PATH
# 4. Reinicie o terminal
```

**Linux:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 2. Instalar Dependências Python

```bash
cd "C:\Users\lucas\Desktop\EVE - AI"

pip install discord.py[voice] PyNaCl faster-whisper numpy python-dotenv
```

### 3. Configurar Token do Bot

Edite o arquivo `.env`:

```env
DISCORD_BOT_TOKEN=seu_token_aqui
```

### 4. Executar o Bot

```bash
python eve_discord_bot.py
```

### 5. Usar no Discord

```
!join        # EVE entra no canal
!listen      # EVE começa a ouvir
```

Pronto! 🎉

---

## 🔍 Verificar Instalação

Execute o teste:

```bash
python testar_voice_system.py
```

Se aparecer "✅ Todos os módulos principais estão funcionando!", está tudo certo!

---

## 📖 Próximos Passos

- Leia: [`DISCORD_VOICE_LISTENING.md`](DISCORD_VOICE_LISTENING.md) - Documentação completa
- Veja: [`exemplo_voice_listening.py`](exemplo_voice_listening.py) - Exemplo de código

---

## ❌ Problemas Comuns

### "FFmpeg not found"
**Solução:** Adicione FFmpeg ao PATH e reinicie o terminal.

### "No module named 'discord'"
**Solução:** `pip install discord.py[voice]`

### "No module named 'faster_whisper'"
**Solução:** `pip install faster-whisper`

### Bot não escuta nada
**Solução:** Verifique se:
1. Bot tem permissão "Connect" e "Speak" no servidor
2. Você usou `!listen` (não apenas `!join`)
3. FFmpeg está instalado

---

## 🆘 Suporte

Se nada funcionar, verifique:

1. **Python 3.9+**: `python --version`
2. **FFmpeg**: `ffmpeg -version`
3. **Logs do bot**: Procure por erros no console

---

## 🎯 Resumo dos Comandos

| Comando | Descrição |
|---------|-----------|
| `!join` | Entrar no canal de voz |
| `!listen` | **Iniciar escuta** |
| `!stop_listen` | Parar escuta |
| `!leave` | Sair do canal |
| `!eve [texto]` | Enviar comando de texto |

---

**Dica:** Use `!listen` assim que entrar no canal para ativar a escuta de voz automática!
