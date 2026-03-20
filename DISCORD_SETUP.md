# 🎮 Guia: EVE no Discord com Voz da Francisca

## 📋 Pré-requisitos

- ✅ Edge TTS instalado
- ✅ FFmpeg instalado (`winget install FFmpeg`)
- ✅ Conta Discord
- ⏳ Token do bot (vamos criar)

## 🚀 Configuração em 5 Passos

### **1. Criar Bot no Discord**

1. Acesse: https://discord.com/developers/applications
2. Clique **"New Application"**
3. Nome: **EVE** (ou o que preferir)
4. Vá em **"Bot"** (menu lateral)
5. Clique **"Add Bot"** → **"Yes, do it!"**
6. **IMPORTANTE:** Clique em **"Reset Token"** e copie o token
   - ⚠️ Guarde bem! Só aparece uma vez
7. Role até **Privileged Gateway Intents** e ative:
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent
8. Clique **"Save Changes"**

### **2. Convidar Bot para Servidor**

1. Ainda no Developer Portal, vá em **OAuth2** → **URL Generator**
2. Em **Scopes**, marque:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Em **Bot Permissions**, marque:
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Read Message History
   - ✅ Connect (Voice)
   - ✅ Speak (Voice)
   - ✅ Use Voice Activity
4. **Copie a URL** que apareceu embaixo
5. **Cole no navegador** e escolha seu servidor
6. Autorize o bot

### **3. Configurar Token**

Crie arquivo `.env` na raiz do projeto:

```env
DISCORD_BOT_TOKEN=cole_seu_token_aqui
```

**Exemplo:**
```env
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4.GaBcDe.FgHiJkLmNoPqRsTuVwXyZ123456789
```

### **4. Instalar Dependências**

```bash
# Discord.py com suporte a voz
pip install discord.py[voice]

# PyNaCl (necessário para voz)
pip install PyNaCl

# Certifique-se de ter FFmpeg
ffmpeg -version
```

Se FFmpeg não estiver instalado:
```bash
winget install FFmpeg
```

### **5. Iniciar Bot**

```bash
python eve_discord_bot.py
```

Você deve ver:
```
============================================================
EVE DISCORD BOT - INICIADO
============================================================
✅ Logado como: EVE
✅ ID: 123456789...
✅ Servidores: 1

Carregando EVE...
✅ EVE carregada!
Configurando voz (Francisca)...
✅ Voz configurada!

Comandos disponíveis:
  !eve <pergunta>    - Perguntar algo
  !falar <texto>     - EVE fala algo
  !join              - Entrar no canal de voz
  !leave             - Sair do canal
============================================================
```

## 🎯 Como Usar no Discord

### **Comandos de Texto**

```
!eve Quem foi Albert Einstein?
```
EVE responde no chat.

```
!eve Me explique o que é inteligência artificial
```

### **Comandos de Voz**

1. **Entre em um canal de voz**
2. **No chat, digite:**
   ```
   !join
   ```
3. **EVE entra no canal!**
4. **Peça para falar:**
   ```
   !eve Como funciona a fotossíntese?
   ```
   EVE responde no chat E fala no canal!

5. **Ou faça ela falar algo específico:**
   ```
   !falar Olá a todos! Eu sou a EVE.
   ```

6. **Para sair:**
   ```
   !leave
   ```

### **Exemplo de Uso Completo**

```
Você: !join
EVE: ✅ Conectado ao canal: Geral

Você: !eve O que é Python?
EVE: 🤖 Python é uma linguagem de programação...
     [EVE fala a resposta no canal de voz]

Você: !falar Obrigada pela pergunta!
EVE: 🔊 Falando: Obrigada pela pergunta!
     [EVE fala no canal]

Você: !leave
EVE: 👋 Saindo do canal de voz...
```

## ⚙️ Personalização

### **Trocar Voz**

Edite `eve_discord_bot.py`, linha ~50:

```python
# Trocar Francisca por outra voz
tts = TextToSpeech(engine="edge", voice_model="pt-BR-ThalitaNeural")
```

### **Mudar Prefixo de Comando**

Edite linha ~20:

```python
PREFIX = "!"  # Mude para "/" ou outro
```

### **Ajustar Velocidade da Voz**

```python
tts = TextToSpeech(
    engine="edge",
    voice_model="pt-BR-FranciscaNeural",
    rate=1.2,    # 20% mais rápido
    volume=1.3   # 30% mais alto
)
```

## 🔧 Troubleshooting

### ❌ "DISCORD_BOT_TOKEN não encontrado"

Crie arquivo `.env`:
```env
DISCORD_BOT_TOKEN=seu_token_aqui
```

### ❌ "Privileged intent provided is not enabled"

Volte no Developer Portal → Bot → Ative os Intents.

### ❌ "FFmpeg não encontrado"

```bash
winget install FFmpeg
# Reinicie o terminal
```

### ❌ Bot não entra no canal de voz

Verifique permissões:
- Bot tem permissão "Connect" e "Speak"?
- Canal de voz não está em modo privado?

### ❌ "Erro ao gerar áudio"

Certifique-se:
1. Edge TTS está instalado: `pip install edge-tts`
2. FFmpeg está instalado: `ffmpeg -version`
3. Internet está funcionando (Edge TTS precisa)

## 📊 Recursos do Bot

| Recurso | Status | Nota |
|---------|--------|------|
| Respostas de texto | ✅ | Funciona |
| Voz no Discord | ✅ | Requer FFmpeg |
| Múltiplos servidores | ✅ | Funciona |
| Comandos personalizados | ✅ | Fácil adicionar |
| Ouvir usuários (STT) | ⏳ | Próxima feature |

## 🎯 Próximas Features

Para adicionar reconhecimento de voz (bot ouve usuários):

1. Instale Whisper:
   ```bash
   pip install faster-whisper
   ```

2. O código já está preparado em `voice/discord_voice.py`

3. Veja documentação completa: `voice/README.md`

## 💡 Dicas

### Manter Bot Online 24/7

Para manter rodando, use:
- **Railway.app** (gratuito)
- **Heroku**
- **VPS** (Contabo, DigitalOcean)

### Logs

Os logs ficam no console. Para salvar:

```bash
python eve_discord_bot.py > bot.log 2>&1
```

### Múltiplos Servidores

O bot funciona em todos os servidores onde você convidou!

## 📝 Resumo de Comandos

```
!eve <pergunta>     - Perguntar algo à EVE
!falar <texto>      - EVE fala algo
!join               - Entrar no canal de voz
!leave              - Sair do canal
!help               - Ver ajuda
```

## 🎉 Pronto!

Seu bot está funcionando! A EVE agora está no Discord com a voz da Francisca! 🎤✨

---

**Precisa de ajuda? Abra uma issue no GitHub ou consulte a documentação.**
