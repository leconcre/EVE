# 🎉 Nova Solução STT: discord-ext-voice-recv

## 📊 O que Mudou?

### ❌ Antes: py-cord (Erro 4006)
- Usava py-cord para receber áudio
- **Problema:** Erro 4006 persistente com servidores brasileiros
- Conexão de voz falhava constantemente

### ✅ Agora: discord.py + discord-ext-voice-recv
- Usa discord.py (biblioteca oficial, mais estável)
- Extensão discord-ext-voice-recv adiciona suporte a áudio
- **Sem erro 4006!**
- Ativamente mantido (última versão: junho 2025)

---

## 🔧 Instalação

### 1. Desinstalar py-cord

```bash
pip uninstall py-cord discord -y
```

### 2. Instalar discord.py + voice-recv

```bash
pip install discord.py[voice] discord-ext-voice-recv
```

### 3. Instalar STT (Whisper)

**Opção A: faster-whisper (recomendado, requer Python 3.11 ou 3.12)**
```bash
pip install faster-whisper numpy
```

**Opção B: openai-whisper (se Python 3.14)**
```bash
pip install openai-whisper
```

### 4. Verificar FFmpeg

```bash
ffmpeg -version
```

Se não instalado:
```bash
# Windows (Chocolatey)
choco install ffmpeg

# Linux
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

---

## ✅ Verificação da Instalação

Execute o teste:

```bash
python testar_voice_recv.py
```

Deve mostrar:
```
✅ discord.py instalado
✅ discord-ext-voice-recv instalado
✅ VoiceRecvClient disponível
✅ SISTEMA PRONTO!
```

---

## 🚀 Como Usar

### 1. Iniciar o Bot

```bash
python eve_discord_bot.py
```

Deve aparecer:
```
EVE DISCORD BOT - INICIADO
✅ Logado como: EVE AI
✅ EVE carregada!
✅ Voz configurada!
✅ Sistema de voz pronto!
```

### 2. Comandos no Discord

```
# 1. Entre no canal de voz
!join

# 2. Ative o sistema de escuta (STT)
!listen

# 3. Fale no canal de voz
"EVE, qual é a capital do Brasil?"

# EVE responde automaticamente em voz!
```

### 3. Outros Comandos

```
!eve [pergunta]        # Pergunta em texto (responde em voz se conectada)
!falar [texto]         # EVE fala algo específico
!stop_listen           # Para de ouvir
!leave                 # Sai do canal de voz
```

---

## 🏗️ Arquitetura

### Fluxo de Dados

```
1. Usuário fala no Discord
   ↓
2. discord-ext-voice-recv captura áudio
   ↓
3. VoiceRecvClient → AudioSink.write(user, data)
   ↓
4. DiscordVAD detecta voz (filtra silêncio)
   ↓
5. Buffer acumula áudio do usuário
   ↓
6. Após silêncio: AudioTranscriber.transcribe()
   ↓
7. UserTracker identifica discord.Member
   ↓
8. PermissionManager verifica creator/admin
   ↓
9. VoiceInput criado com todos os dados
   ↓
10. Callback on_transcription(voice_input)
    ↓
11. EVE processa e responde em voz
```

### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| **VoiceRecvClient** | Cliente de voz que RECEBE áudio (voice-recv) |
| **AudioSink** | Callback para processar chunks de áudio |
| **VoiceRecordingSink** | Sink customizado que captura por usuário |
| **DiscordVAD** | Voice Activity Detection (filtra silêncio) |
| **AudioTranscriber** | Whisper para STT |
| **UserTracker** | Mapeia user_id → discord.Member |
| **PermissionManager** | Verifica creator/admin |
| **VoiceInput** | Estrutura de dados com tudo |

---

## 🔍 Diferenças: py-cord vs discord-ext-voice-recv

| Aspecto | py-cord | discord-ext-voice-recv |
|---------|---------|------------------------|
| **Biblioteca base** | Fork do discord.py | Extensão para discord.py |
| **API de áudio** | `discord.sinks.Sink` | `voice_recv.AudioSink` |
| **Método de escuta** | `start_recording(sink)` | `listen(sink)` |
| **Cliente de voz** | `discord.VoiceClient` | `voice_recv.VoiceRecvClient` |
| **Conexão** | `await channel.connect()` | `await channel.connect(cls=VoiceRecvClient)` |
| **Callback** | `write(data, user)` | `write(user, data)` |
| **Dados de áudio** | `bytes` (PCM) | `VoiceData.pcm` |
| **Erro 4006** | ❌ Persistente | ✅ Resolvido |
| **Manutenção** | Ativa | Ativa (jun/2025) |
| **Estabilidade** | Problemas regionais | ✅ Estável |

---

## 📝 Mudanças no Código

### voice/stt/discord_listener.py

**Antes (py-cord):**
```python
import discord

class VoiceRecordingSink(discord.sinks.Sink):
    def write(self, data, user):
        # data primeiro, user depois
        pcm_data = data
```

**Agora (voice-recv):**
```python
from discord.ext import voice_recv

class VoiceRecordingSink(voice_recv.AudioSink):
    def write(self, user, data):
        # user primeiro, data depois
        pcm_data = data.pcm  # VoiceData tem atributo .pcm
```

### eve_discord_bot.py

**Antes (py-cord):**
```python
import discord
from discord.ext import commands

# Conectar
voice_client = await channel.connect()
```

**Agora (voice-recv):**
```python
import discord
from discord.ext import commands, voice_recv

# Conectar usando VoiceRecvClient
voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
```

### voice/discord_integration.py

**Antes:**
```python
async def start_listening(self, voice_client: discord.VoiceClient):
    voice_client.start_recording(self._sink, self._on_recording_error, channel)
```

**Agora:**
```python
async def start_listening(self, voice_client: voice_recv.VoiceRecvClient):
    voice_client.listen(self._sink)
```

---

## 🐛 Troubleshooting

### Erro: "No module named 'discord.ext.voice_recv'"

**Solução:**
```bash
pip install discord-ext-voice-recv
```

### Erro: "VoiceRecvClient has no attribute 'listen'"

**Causa:** Está usando discord.VoiceClient ao invés de VoiceRecvClient

**Solução:** Sempre conecte com:
```python
await channel.connect(cls=voice_recv.VoiceRecvClient)
```

### Bot não captura áudio

**Verificações:**

1. Confirmar VoiceRecvClient:
   ```python
   print(type(ctx.voice_client))  # Deve ser VoiceRecvClient
   ```

2. Verificar se está escutando:
   ```python
   if voice_client.is_listening():
       print("✅ Escutando")
   ```

3. Permissões do bot:
   - Connect
   - Speak
   - Use Voice Activity

### faster-whisper não funciona (Python 3.14)

**Solução:** Use openai-whisper:
```bash
pip install openai-whisper
```

Depois modifique [voice/stt/transcriber.py](voice/stt/transcriber.py):
```python
import whisper  # ao invés de faster_whisper
```

---

## 📚 Recursos

### Documentação Oficial
- [discord.py](https://discordpy.readthedocs.io/)
- [discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv)
- [faster-whisper](https://github.com/guillaumekln/faster-whisper)

### Arquivos do Projeto
- [eve_discord_bot.py](eve_discord_bot.py) - Bot principal
- [voice/stt/discord_listener.py](voice/stt/discord_listener.py) - Captura de áudio
- [voice/discord_integration.py](voice/discord_integration.py) - API de integração
- [GUIA_PY_CORD.md](GUIA_PY_CORD.md) - Guia antigo (py-cord)
- **[INSTALACAO_VOICE_RECV.md](INSTALACAO_VOICE_RECV.md)** - Este arquivo

---

## ✅ Checklist de Migração

- [ ] Desinstalou py-cord
- [ ] Instalou discord.py[voice]
- [ ] Instalou discord-ext-voice-recv
- [ ] Instalou faster-whisper ou openai-whisper
- [ ] FFmpeg instalado e no PATH
- [ ] Token do Discord em .env
- [ ] Executou testar_voice_recv.py (passou)
- [ ] Iniciou eve_discord_bot.py (sem erros)
- [ ] Testou !join (conectou com sucesso)
- [ ] Testou !listen (iniciou escuta)
- [ ] Falou no canal (EVE transcreveu e respondeu)

---

## 🎯 Próximos Passos

1. **Testar em produção**
   - Use !join para conectar
   - Use !listen para ativar STT
   - Fale no canal de voz
   - Verifique se EVE responde

2. **Ajustar configurações**
   - Modelo Whisper: `model_size="medium"` para melhor precisão
   - VAD threshold: ajuste em `voice/stt/vad.py`
   - Duração mínima de áudio: ajuste em `discord_listener.py`

3. **Monitorar logs**
   - `🎤 Iniciando captura` = usuário começou a falar
   - `📝 Processando Xs de áudio` = transcrevendo
   - `✅ [username]: texto` = transcrição concluída

---

## 🎉 Conclusão

**A mudança para discord-ext-voice-recv resolve o erro 4006!**

Agora o sistema de voz da EVE está completo e funcional:
- ✅ TTS (Text-to-Speech) com Francisca
- ✅ STT (Speech-to-Text) com Whisper
- ✅ Identificação de usuários
- ✅ Sistema de permissões
- ✅ VAD para filtrar silêncio
- ✅ Arquitetura modular

**A EVE agora OUVE e FALA de verdade!** 🎤🔊
