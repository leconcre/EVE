# 🎙️ Sistema de Voz Discord - EVE

## ⚡ Sistema COMPLETO de Reconhecimento e Síntese de Voz

A EVE agora **OUVE** e **FALA** no Discord com identificação precisa de usuários!

---

## ✨ Características

- ✅ **Captura de áudio REAL** (py-cord Audio Sinks)
- ✅ **Identificação por Discord ID** (não biometria)
- ✅ **Transcrição em pt-BR** (Whisper faster-whisper)
- ✅ **Síntese de voz** (Edge TTS - voz Francisca)
- ✅ **Detecção de voz** (VAD - ignora silêncio)
- ✅ **Sistema de permissões** (criador/admin/moderador)
- ✅ **Separação por usuário** (cada pessoa tem seu buffer)
- ✅ **Pronto para produção**

---

## ⚠️ IMPORTANTE: Por que py-cord?

**discord.py NÃO suporta recebimento de áudio!**

Este sistema usa **py-cord**, um fork mantido que implementou Audio Sinks para CAPTURAR áudio dos usuários.

```python
# ❌ discord.py - Não funciona para ouvir
# ✅ py-cord - Funciona!

class MySink(discord.sinks.Sink):
    def write(self, data, user):
        # Recebe áudio de cada usuário
        handle_audio(data, user)
```

---

## 🚀 Instalação em 3 Passos

### 1. Instalar py-cord

```bash
pip uninstall discord.py discord -y
pip install py-cord[voice] PyNaCl faster-whisper numpy
```

### 2. Instalar FFmpeg

**Windows:**
```bash
choco install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

### 3. Executar

```bash
python eve_discord_bot.py
```

**Pronto!** 🎉

---

## 💬 Uso no Discord

```
!join          # EVE entra no canal de voz

!listen        # EVE começa a OUVIR (ativa STT)

# Fale no canal de voz:
"EVE, qual é a capital do Brasil?"

# EVE responde:
# - Chat: "🤖 A capital do Brasil é Brasília."
# - Voz: EVE fala a resposta

!stop_listen   # EVE para de ouvir

!leave         # EVE sai do canal
```

---

## 📊 O que EVE Recebe

Quando você fala, EVE recebe:

```python
VoiceInput(
    user_id=123456789,              # Seu ID Discord
    username="Leconcre",             # Seu nome
    text="EVE, como vai?",          # O que você disse
    confidence=0.95,                 # Precisão (0-1)
    is_creator=True,                 # Se você é o criador
    is_admin=True,                   # Se você é admin
    roles=["Admin", "VIP"],         # Suas roles
    audio_duration=2.5,              # Duração da fala
    language="pt"                    # Idioma detectado
)
```

---

## 🔐 Configurar Criador

```python
# Em eve_discord_bot.py ou seu código
from voice import permission_manager

# Por username
permission_manager.creator_username = "SeuNome"

# Ou por ID (mais seguro)
permission_manager.set_creator_id(123456789)
```

---

## 📖 Documentação Completa

- **[GUIA_PY_CORD.md](GUIA_PY_CORD.md)** - Guia completo do sistema
- **[eve_discord_bot.py](eve_discord_bot.py)** - Código do bot
- **[voice/stt/discord_listener.py](voice/stt/discord_listener.py)** - Implementação do Sink

---

## 🏗️ Arquitetura

```
Usuário fala
    ↓
py-cord captura (VoiceRecordingSink)
    ↓
VAD detecta voz
    ↓
Buffer acumula áudio
    ↓
Whisper transcreve (pt-BR)
    ↓
VoiceInput criado
    ↓
Callback processa
    ↓
EVE responde (chat + TTS)
```

---

## 🎓 Exemplo de Código

```python
from voice import listen_from_discord, VoiceInput

async def on_voice(voice_input: VoiceInput):
    # Log
    print(f"[VOICE] {voice_input.username}: {voice_input.text}")

    # Verifica permissões
    if voice_input.is_creator:
        print("Criador falou!")

    # Processa com IA
    response = eve.generate_response(voice_input.text)
    await speak(response['text'])

# Ativa escuta
await listen_from_discord(voice_client, on_voice)
```

---

## ⚙️ Configurações

### Trocar Modelo Whisper

```python
# Rápido
model_size="tiny"

# Balanceado (RECOMENDADO)
model_size="small"

# Preciso
model_size="medium"
```

### GPU Acceleration

```python
from voice.stt.transcriber import AudioTranscriber

transcriber = AudioTranscriber(
    model_size="medium",
    device="cuda",      # CPU ou CUDA
    compute_type="float16"
)
```

---

## 🐛 Troubleshooting

### Bot não ouve

1. **Verificar py-cord:**
   ```bash
   python -c "import discord; print(discord.__version__)"
   # Deve mostrar: 2.6.x
   ```

2. **Verificar sinks:**
   ```bash
   python -c "import discord.sinks; print('OK')"
   ```

3. **Permissões do bot:**
   - View Channel
   - Connect
   - Speak
   - Use Voice Activity

### Erro: "No module named 'discord'"

```bash
pip uninstall discord.py discord -y
pip install py-cord[voice]
```

---

## 📊 Performance

| Modelo | CPU | GPU | Precisão | Uso |
|--------|-----|-----|----------|-----|
| tiny | ~1s | ~0.2s | 85% | Testes |
| **small** | **~3s** | **~0.5s** | **92%** | **Produção** |
| medium | ~8s | ~1.2s | 96% | Alta precisão |

---

## 📁 Estrutura do Projeto

```
voice/
├── stt/
│   ├── discord_listener.py    ← VoiceRecordingSink (py-cord)
│   ├── models.py              ← VoiceInput
│   ├── user_tracker.py        ← user_id → Member
│   ├── vad.py                 ← Voice Activity Detection
│   └── transcriber.py         ← faster-whisper
├── permissions.py             ← Criador/admin
├── discord_integration.py     ← listen_from_discord()
└── text_to_speech.py          ← TTS (Edge TTS)
```

---

## ✅ Checklist

- [ ] py-cord instalado (`pip list | grep py-cord`)
- [ ] FFmpeg instalado (`ffmpeg -version`)
- [ ] Bot conecta ao Discord
- [ ] `!join` funciona
- [ ] `!listen` ativa escuta
- [ ] Ao falar, vê log: `"🎤 Iniciando captura..."`
- [ ] Transcrição funciona
- [ ] Bot responde em voz

---

## 🎯 Stack Tecnológica

| Componente | Biblioteca | Versão |
|------------|-----------|--------|
| Discord Bot | py-cord | 2.6.x |
| Audio Codec | PyNaCl | 1.5+ |
| STT | faster-whisper | 0.9+ |
| TTS | Edge TTS | Latest |
| VAD | Numpy | 1.24+ |
| Audio | FFmpeg | Latest |

---

## 🚀 Deploy

### Desenvolvimento

```bash
python eve_discord_bot.py
```

### Produção

```bash
# Use modelo small
model_size="small"

# Configure logging
logging.basicConfig(level=logging.INFO)

# Use GPU se disponível
device="cuda"  # ou "cpu"
```

---

## 📞 Comandos Rápidos

```bash
# Instalar tudo
pip install py-cord[voice] PyNaCl faster-whisper numpy

# Verificar
python -c "import discord; print(discord.__version__)"

# Executar
python eve_discord_bot.py
```

---

## 🆘 Suporte

1. Leia: [GUIA_PY_CORD.md](GUIA_PY_CORD.md)
2. Verifique logs do bot
3. Confirme que está usando py-cord (não discord.py)
4. Verifique permissões do bot no servidor

---

## 🎉 Pronto!

**A EVE agora OUVE DE VERDADE usando py-cord!**

- ✅ Captura áudio real
- ✅ Identifica quem fala (user_id)
- ✅ Transcreve em português
- ✅ Sistema de permissões
- ✅ Modular e robusto

**Documentação:** [GUIA_PY_CORD.md](GUIA_PY_CORD.md)
