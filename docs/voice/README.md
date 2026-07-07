# 🎙️ EVE Voice Module

Sistema completo de voz (STT + TTS) para a EVE AI, com suporte a Discord.

## 📋 Índice

- [Características](#características)
- [Instalação](#instalação)
- [Uso Rápido](#uso-rápido)
- [Configuração](#configuração)
- [Exemplos](#exemplos)
- [Integração com Discord](#integração-com-discord)
- [Arquitetura](#arquitetura)
- [Troubleshooting](#troubleshooting)

---

## ✨ Características

### 🎤 Speech-to-Text (STT)
- **Whisper OpenAI** (faster-whisper para performance)
- Suporte a português (pt-BR)
- Detecção automática de início/fim da fala (VAD)
- Cache de transcrições para performance
- Múltiplos modelos disponíveis (tiny → large-v3)

### 🔊 Text-to-Speech (TTS)
- **Piper TTS** (offline, alta qualidade)
- Suporte alternativo: Coqui TTS, gTTS, pyttsx3
- Voz em português brasileiro
- Controle de velocidade e volume
- Fácil troca de vozes/engines

### 🎮 Integração Discord
- Bot completo com comandos de voz
- Entra/sai de canais automaticamente
- Ouve usuários e transcreve em tempo real
- Responde usando TTS no canal
- Suporte a múltiplos usuários simultâneos

### 🛠️ Recursos Técnicos
- **VAD (Voice Activity Detection)**: Silero VAD + WebRTC VAD + Energy-based
- **Processamento de áudio**: redução de ruído, normalização, trim de silêncio
- **Modular**: fácil trocar engines de STT e TTS
- **Async**: suporte completo a operações assíncronas
- **Cross-platform**: funciona no Windows, Linux e macOS

---

## 🚀 Instalação

### 1️⃣ Requisitos Básicos

**Python 3.8+** é necessário.

```bash
# Clone o repositório (se ainda não tiver)
cd "EVE - AI"
```

### 2️⃣ Instalar Dependências

#### **Opção A: Instalação Completa (Recomendado)**

```bash
# Bibliotecas de áudio
pip install pyaudio sounddevice

# Speech-to-Text (Whisper)
pip install faster-whisper
# ou (alternativa mais leve):
pip install openai-whisper

# Text-to-Speech
pip install pyttsx3  # Offline, fácil de usar
pip install gtts     # Online, Google TTS (opcional)
pip install TTS      # Coqui TTS (opcional, melhor qualidade)

# VAD (Voice Activity Detection)
pip install torch torchaudio  # Para Silero VAD
pip install webrtcvad         # VAD alternativo

# Processamento de áudio
pip install numpy scipy
pip install noisereduce  # Redução de ruído (opcional)

# Discord (se for usar)
pip install discord.py[voice]
```

#### **Opção B: Instalação Mínima (Teste Rápido)**

```bash
pip install pyaudio numpy faster-whisper pyttsx3
```

### 3️⃣ Instalar FFmpeg

O FFmpeg é necessário para processar áudio.

**Windows:**
```bash
# Usando winget
winget install FFmpeg

# Ou baixe de: https://ffmpeg.org/download.html
# E adicione ao PATH
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 4️⃣ Instalar Piper TTS (Opcional, mas Recomendado)

**Windows:**
```bash
winget install rhasspy.piper
```

**Linux/macOS:**
```bash
# Via Python
pip install piper-tts

# Ou compile do source:
git clone https://github.com/rhasspy/piper.git
cd piper/src/python
pip install -e .
```

### 5️⃣ Configurar Discord Bot (Opcional)

Se quiser usar integração com Discord:

1. Acesse [Discord Developer Portal](https://discord.com/developers/applications)
2. Crie uma nova aplicação
3. Vá em "Bot" e clique "Add Bot"
4. Copie o token
5. Crie um arquivo `.env` na raiz do projeto:

```env
DISCORD_BOT_TOKEN=seu_token_aqui
```

6. Convide o bot para seu servidor:
   - Vá em "OAuth2" → "URL Generator"
   - Marque: `bot` e `applications.commands`
   - Permissões: `Connect`, `Speak`, `Use Voice Activity`
   - Copie e acesse a URL gerada

---

## ⚡ Uso Rápido

### Exemplo Mais Simples

```python
from voice import listen, speak

# Ouvir
text = listen()
print(f"Você disse: {text}")

# Falar
speak("Olá! Eu sou a EVE.")
```

### Integração com EVE

```python
from core.eve import Eve
from voice import create_voice_loop

# Inicializa EVE
eve = Eve()

# Cria loop de voz (ouve → processa → responde)
create_voice_loop(eve)
```

### Executar Exemplos

```bash
# Exemplo simples
python example_voice.py --mode simple

# Com EVE completa
python example_voice.py --mode eve

# Exemplo avançado
python example_voice.py --mode advanced

# Bot do Discord
python example_voice.py --mode discord

# Informações do sistema
python example_voice.py --mode info
```

---

## ⚙️ Configuração

Todas as configurações estão em [`voice/config.py`](config.py).

### Principais Configurações

```python
# Modelo Whisper (qualidade vs velocidade)
WHISPER_MODEL = "small"  # tiny, base, small, medium, large-v3

# Taxa de amostragem
SAMPLE_RATE = 16000  # 16kHz (padrão para reconhecimento de voz)

# VAD (sensibilidade de detecção de voz)
VAD_AGGRESSIVENESS = 2  # 0 (sensível) a 3 (rigoroso)

# Silêncio para finalizar gravação
SILENCE_DURATION = 1.5  # segundos

# Engine de TTS
# Use "piper", "coqui", "gtts" ou "pyttsx3"
```

### Perfis Prontos

```python
from voice import config

# Máxima velocidade (sacrifica qualidade)
config.apply_profile("speed")

# Máxima qualidade (sacrifica velocidade)
config.apply_profile("quality")

# Balanceado (padrão)
config.apply_profile("balanced")
```

---

## 📚 Exemplos

### 1. Ouvir e Transcrever

```python
from voice import listen

while True:
    text = listen(timeout=30)
    if text:
        print(f"📝 {text}")
```

### 2. Falar com Diferentes Engines

```python
from voice import speak

# pyttsx3 (offline, básico)
speak("Olá!", engine="pyttsx3")

# Piper (offline, melhor qualidade)
speak("Olá!", engine="piper")

# gTTS (online, Google)
speak("Olá!", engine="gtts")
```

### 3. Controle Avançado

```python
from voice import VoiceListener, SpeechToText, TextToSpeech

# Listener customizado
listener = VoiceListener()
audio = listener.listen_once(timeout=30)

# STT com modelo específico
stt = SpeechToText(model_name="medium")
result = stt.transcribe(audio)
print(result['text'])

# TTS com controle fino
tts = TextToSpeech(engine="piper", rate=1.5, volume=0.8)
tts.synthesize("Teste", play=True)
```

### 4. Salvar/Carregar Áudio

```python
from voice import listen, save_audio, load_audio
from pathlib import Path

# Grava e salva
text, audio = listen(return_audio=True)
save_audio(audio, Path("gravacao.wav"))

# Carrega e transcreve
from voice import SpeechToText
stt = SpeechToText()
result = stt.transcribe("gravacao.wav")
```

### 5. Loop Customizado com EVE

```python
from core.eve import Eve
from voice import listen, speak

eve = Eve()

while True:
    # Ouve
    user_input = listen()
    if not user_input:
        continue

    print(f"👤 Você: {user_input}")

    # Processa
    response = eve.generate_response(user_input)
    eve_text = response.get("text", "")

    print(f"🤖 EVE: {eve_text}")

    # Fala
    speak(eve_text)
```

---

## 🎮 Integração com Discord

### Criar Bot Básico

```python
from voice import create_voice_bot

# Callback para processar transcrições
async def on_user_message(user_id, text, ctx):
    print(f"Usuário {user_id} disse: {text}")

    # Processa com EVE (exemplo)
    # eve_response = eve.generate_response(text)
    # await speak_in_channel(eve_response['text'])

# Cria e inicia bot
bot = create_voice_bot(on_transcription=on_user_message)
bot.run()
```

### Comandos Disponíveis

Depois de iniciar o bot, use no Discord:

- `!join` - Bot entra no seu canal de voz
- `!leave` - Bot sai do canal
- `!speak <texto>` - Bot fala algo
- `!listen` - Bot começa a ouvir
- `!stop` - Bot para de ouvir

### Bot Completo com EVE

```python
from voice import create_voice_bot
from core.eve import Eve

# Inicializa EVE
eve = Eve()

# Callback que integra com EVE
async def process_and_respond(user_id, text, ctx):
    # Ignora mensagens vazias
    if not text:
        return

    # Processa com EVE
    response = eve.generate_response(text)
    eve_text = response.get("text", "")

    # Envia no chat
    await ctx.send(f"🤖 **EVE:** {eve_text}")

    # Fala no canal (se estiver conectado)
    # TODO: Implementar speak_in_channel

# Cria bot
bot = create_voice_bot(on_transcription=process_and_respond)
bot.run()
```

---

## 🏗️ Arquitetura

```
voice/
├── __init__.py           # API principal (listen, speak)
├── config.py             # Configurações centralizadas
├── listener.py           # Captura de áudio do microfone
├── speech_to_text.py     # STT com Whisper
├── text_to_speech.py     # TTS (Piper, Coqui, etc.)
├── discord_voice.py      # Integração Discord
├── audio_utils.py        # VAD, processamento, utils
├── models/               # Modelos baixados (Whisper, Piper)
└── cache/                # Cache de áudio e transcrições
```

### Fluxo de Dados

```
Microfone → Listener (VAD) → Áudio → STT (Whisper) → Texto
                                                        ↓
                                                       EVE
                                                        ↓
                                              Texto ← TTS (Piper) ← Alto-falante
```

### Componentes Principais

1. **VoiceListener**: Captura áudio com detecção automática de voz
2. **SpeechToText**: Transcreve áudio usando Whisper
3. **TextToSpeech**: Sintetiza voz usando múltiplas engines
4. **DiscordVoiceBot**: Bot completo para Discord
5. **VoiceActivityDetector**: Detecta quando há voz no áudio

---

## 🔧 Troubleshooting

### ❌ PyAudio não instala no Windows

```bash
# Baixe o wheel pré-compilado:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

# Instale:
pip install PyAudio-0.2.11-cp39-cp39-win_amd64.whl
```

### ❌ "No module named 'torch'"

```bash
# Instale PyTorch:
pip install torch torchaudio
```

### ❌ Piper não encontrado

```bash
# Windows:
winget install rhasspy.piper

# Ou use pyttsx3 como alternativa:
from voice import speak
speak("Teste", engine="pyttsx3")
```

### ❌ FFmpeg não encontrado

```bash
# Verifique se está no PATH:
ffmpeg -version

# Se não estiver, adicione ao PATH ou reinstale:
winget install FFmpeg
```

### ❌ Whisper muito lento

```python
# Use modelo menor:
from voice import SpeechToText
stt = SpeechToText(model_name="tiny")  # Muito mais rápido

# Ou use CPU com otimizações:
stt = SpeechToText(
    model_name="base",
    compute_type="int8",  # Quantização
    device="cpu"
)
```

### ❌ Discord bot não conecta

1. Verifique se o token está correto em `.env`
2. Certifique-se que o bot foi convidado ao servidor
3. Verifique permissões (Connect, Speak, Use Voice Activity)
4. Teste a instalação:

```python
import discord
print(discord.__version__)  # Deve ser >= 2.0
```

### ❌ Áudio muito baixo/alto

```python
from voice import speak

# Ajusta volume
speak("Teste", volume=1.5)  # 150% do volume normal

# Ou configura globalmente:
from voice import config
config.PIPER_VOLUME = 1.5
```

### ❌ VAD muito sensível (grava ruído)

```python
from voice import config

# Aumenta rigor (menos falsos positivos)
config.VAD_AGGRESSIVENESS = 3
config.SILERO_THRESHOLD = 0.7
```

---

## 📊 Performance

### Modelos Whisper

| Modelo   | Tamanho | Velocidade | Precisão | VRAM   |
|----------|---------|------------|----------|--------|
| tiny     | 39MB    | ⚡⚡⚡       | ⭐⭐     | ~1GB   |
| base     | 74MB    | ⚡⚡        | ⭐⭐⭐    | ~1GB   |
| small    | 244MB   | ⚡         | ⭐⭐⭐⭐   | ~2GB   |
| medium   | 769MB   | 🐌         | ⭐⭐⭐⭐⭐  | ~5GB   |
| large-v3 | 1550MB  | 🐌🐌       | ⭐⭐⭐⭐⭐  | ~10GB  |

**Recomendado para uso geral:** `small` (bom equilíbrio)

### Engines TTS

| Engine   | Qualidade | Velocidade | Offline | Idiomas |
|----------|-----------|------------|---------|---------|
| Piper    | ⭐⭐⭐⭐    | ⚡⚡       | ✅      | 30+     |
| Coqui    | ⭐⭐⭐⭐⭐   | ⚡         | ✅      | 50+     |
| pyttsx3  | ⭐⭐       | ⚡⚡⚡      | ✅      | Sistema |
| gTTS     | ⭐⭐⭐     | 🐌 (online)| ❌      | 100+    |

**Recomendado:** `piper` (offline, boa qualidade)

---

## 🤝 Contribuindo

Sugestões e melhorias são bem-vindas!

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/melhorias`)
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

---

## 📄 Licença

Este módulo faz parte do projeto EVE AI.

---

## 🙏 Créditos

- **Whisper**: OpenAI
- **Piper TTS**: Rhasspy
- **Silero VAD**: Silero Team
- **discord.py**: Rapptz

---

**Desenvolvido com ❤️ para a EVE AI**
