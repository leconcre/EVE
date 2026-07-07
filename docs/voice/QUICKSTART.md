# 🚀 Quick Start - EVE Voice Module

Guia rápido de 5 minutos para começar a usar o módulo de voz.

## ⏱️ 5 Minutos para Começar

### 1️⃣ Instalar Dependências (2 min)

```bash
# Instale FFmpeg primeiro (se não tiver)
winget install FFmpeg

# Instale dependências mínimas
pip install -r voice/requirements-minimal.txt
```

### 2️⃣ Teste Básico (1 min)

Crie um arquivo `test_voice.py`:

```python
from voice import listen, speak

# Teste de fala
speak("Olá! Eu sou a EVE. Fale algo para mim.")

# Teste de escuta
text = listen(timeout=10)
print(f"Você disse: {text}")
```

Execute:

```bash
python test_voice.py
```

### 3️⃣ Integrar com EVE (2 min)

```python
from core.eve import Eve
from voice import listen, speak

# Inicializa EVE
eve = Eve()
speak("EVE inicializada! Pode perguntar algo.")

# Loop de conversa
while True:
    # Ouve
    user_text = listen()
    if not user_text:
        continue

    print(f"Você: {user_text}")

    # Processa
    response = eve.generate_response(user_text)
    eve_text = response['text']

    print(f"EVE: {eve_text}")

    # Responde
    speak(eve_text)
```

**Pronto!** 🎉 Agora você tem uma EVE falante.

---

## 🎯 Casos de Uso Comuns

### Apenas Ouvir

```python
from voice import listen

text = listen()
print(text)
```

### Apenas Falar

```python
from voice import speak

speak("Olá, mundo!")
```

### Transcrever Arquivo de Áudio

```python
from voice import SpeechToText

stt = SpeechToText()
result = stt.transcribe("audio.wav")
print(result['text'])
```

### Gravar Áudio

```python
from voice import record_audio
from pathlib import Path

audio = record_audio(save_to=Path("gravacao.wav"))
```

### Listar Microfones

```python
from voice import list_microphones

mics = list_microphones()
for mic in mics:
    print(f"[{mic['index']}] {mic['name']}")
```

---

## 🔧 Configuração Rápida

### Trocar Modelo Whisper

```python
from voice import SpeechToText

# Modelo mais rápido (menos preciso)
stt = SpeechToText(model_name="tiny")

# Modelo mais lento (mais preciso)
stt = SpeechToText(model_name="medium")
```

### Trocar Engine TTS

```python
from voice import speak

# pyttsx3 (offline, básico)
speak("Teste", engine="pyttsx3")

# gTTS (online, Google)
speak("Teste", engine="gtts")

# Piper (offline, melhor qualidade)
speak("Teste", engine="piper")
```

### Ajustar Sensibilidade do VAD

```python
from voice import config

# Menos sensível (menos falsos positivos)
config.VAD_AGGRESSIVENESS = 3
config.SILERO_THRESHOLD = 0.7

# Mais sensível (captura mais facilmente)
config.VAD_AGGRESSIVENESS = 1
config.SILERO_THRESHOLD = 0.3
```

---

## 🎮 Discord em 3 Passos

### 1. Configure o Token

Crie `.env`:

```env
DISCORD_BOT_TOKEN=seu_token_aqui
```

### 2. Crie o Bot

```python
from voice import create_voice_bot

bot = create_voice_bot()
bot.run()
```

### 3. Use no Discord

```
!join    - Bot entra no canal
!speak Olá a todos!
!listen  - Bot começa a ouvir
```

---

## ❓ Problemas Comuns

### ❌ PyAudio não instala

```bash
# Baixe wheel pré-compilado:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

pip install PyAudio-0.2.11-cp39-cp39-win_amd64.whl
```

### ❌ Whisper muito lento

```python
# Use modelo menor
from voice import SpeechToText
stt = SpeechToText(model_name="tiny")
```

### ❌ Piper não encontrado

```python
# Use pyttsx3 como alternativa
from voice import speak
speak("Teste", engine="pyttsx3")
```

### ❌ Muito ruído/falsos positivos

```python
from voice import config
config.VAD_AGGRESSIVENESS = 3  # Mais rigoroso
```

---

## 📚 Próximos Passos

1. **Leia a documentação completa**: [`README.md`](README.md)
2. **Veja os exemplos**: [`example_voice.py`](../example_voice.py)
3. **Configure perfis**: [`config.py`](config.py)
4. **Instale dependências completas**: `pip install -r voice/requirements.txt`

---

**Divirta-se com a EVE! 🎉**
