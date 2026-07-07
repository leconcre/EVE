# 🎧 Sistema de Voz EVE com PY-CORD - Guia Completo

## ⚠️ IMPORTANTE: Por que PY-CORD?

### ❌ discord.py NÃO suporta recebimento de áudio

A biblioteca `discord.py` oficial **NÃO tem suporte adequado para RECEBER áudio** dos usuários. Ela apenas suporta ENVIAR áudio (TTS/música).

### ✅ py-cord SUPORTA Audio Sinks

`py-cord` é um fork mantido do discord.py que **implementou Audio Sinks**, permitindo que bots **OUÇAM** usuários em canais de voz.

```python
# Com py-cord, você pode fazer:
class MySink(discord.sinks.Sink):
    def write(self, data, user):
        # data = áudio do usuário
        # user = discord.Member
        process_audio(data, user)

voice_client.start_recording(MySink())
```

---

## 🚀 Instalação Rápida

### 1. Remover discord.py (se instalado)

```bash
pip uninstall discord.py discord -y
```

### 2. Instalar py-cord com suporte a voz

```bash
pip install py-cord[voice] PyNaCl
```

### 3. Instalar dependências do sistema STT

```bash
pip install faster-whisper numpy
```

### 4. Instalar FFmpeg

**Windows:**
```powershell
choco install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 5. Verificar Instalação

```bash
python -c "import discord; print(discord.__version__)"
# Deve mostrar algo como: 2.6.1
```

---

## 🎯 Como Funciona

### Arquitetura do Sistema

```
1. Usuário fala no Discord
   ↓
2. py-cord captura áudio via Sink.write(data, user)
   ↓
3. VoiceRecordingSink identifica quem falou (user.id)
   ↓
4. VAD detecta início/fim da fala
   ↓
5. Buffer acumula áudio do usuário
   ↓
6. Whisper transcreve para texto (pt-BR)
   ↓
7. VoiceInput retornado com:
   - user_id
   - username
   - text (transcrito)
   - is_creator / is_admin
   - roles
   ↓
8. Callback processa a entrada
```

### Código do Sink (Simplificado)

```python
class VoiceRecordingSink(discord.sinks.Sink):
    """Captura áudio separado por usuário."""

    def write(self, data, user):
        """
        Chamado automaticamente pelo py-cord.

        Args:
            data: bytes de áudio PCM (48kHz, stereo, 16-bit)
            user: discord.Member ou user_id
        """
        user_id = user if isinstance(user, int) else user.id

        # Verifica se tem voz (VAD)
        if self.vad.is_voice(data):
            # Armazena no buffer do usuário
            self.buffers[user_id].write(data)
        else:
            # Silêncio: processa buffer acumulado
            if user_id in self.buffers:
                audio = self.buffers[user_id].getvalue()
                self.transcribe(audio, user_id)
```

---

## 💻 Uso Básico

### No Discord

```bash
# 1. Iniciar bot
python eve_discord_bot.py

# 2. No Discord, em um canal de texto:
!join          # EVE entra no canal de voz

!listen        # EVE COMEÇA A OUVIR (STT ativado)

# 3. Fale no canal de voz:
"EVE, qual é a capital do Brasil?"

# 4. EVE responde automaticamente:
# - Chat: "🤖 EVE: A capital do Brasil é Brasília."
# - Voz: EVE fala a resposta

!stop_listen   # EVE para de ouvir

!leave         # EVE sai do canal
```

### Logs Esperados

```
[INFO] ✅ VoiceRecordingSink inicializado (py-cord)
[INFO] ✅ ESCUTANDO canal: General
[INFO]    Usuários no canal: ['Leconcre']
[INFO] 🎤 Iniciando captura de áudio: Leconcre (ID: 123456789)
[INFO] 📝 Processando 2.50s de áudio de: Leconcre
[INFO] ✅ Leconcre [CREATOR]: EVE, qual é a capital do Brasil?
[INFO] 🤖 EVE: A capital do Brasil é Brasília.
```

---

## 🔧 Uso Programático

### Exemplo Completo

```python
import discord
from discord.ext import commands
from voice import listen_from_discord, VoiceInput

# Cria bot (py-cord)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Callback quando alguém fala
async def on_user_spoke(voice_input: VoiceInput):
    """
    Chamado quando usuário fala no canal.

    Args:
        voice_input: VoiceInput com todos os dados
    """
    # Log
    print(f"[VOICE] {voice_input.username}: {voice_input.text}")

    # Verifica permissões
    if voice_input.is_creator:
        print("  ^ Criador falou!")

        # Comandos especiais do criador
        if "desligar" in voice_input.text.lower():
            await bot.close()

    # Processa comando com IA
    from core.eve import Eve
    eve = Eve()
    response = eve.generate_response(voice_input.text)

    print(f"[EVE] {response['text']}")

    # Responde em voz (TTS)
    await speak_response(response['text'])

# Comando para ativar escuta
@bot.command()
async def listen(ctx):
    """Ativa sistema de escuta."""
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    # INICIA ESCUTA COM PY-CORD
    await listen_from_discord(
        ctx.voice_client,
        on_transcription=on_user_spoke,
        model_size="small"  # tiny, small, medium, large-v3
    )

    await ctx.send("✅ ESCUTANDO! Fale no canal de voz.")

bot.run(TOKEN)
```

---

## 📊 Estrutura VoiceInput

### Todos os Campos Retornados

```python
from voice import VoiceInput

voice_input = VoiceInput(
    # Identificação do usuário
    user_id=123456789,              # ID único do Discord
    username="Leconcre",             # Nome de exibição

    # Conteúdo transcrito
    text="EVE, como vai?",          # Texto da fala
    confidence=0.95,                 # Confiança (0.0-1.0)
    language="pt",                   # Idioma detectado

    # Permissões
    is_creator=True,                 # Se é o criador do bot
    is_admin=True,                   # Se é admin do servidor
    roles=["Admin", "VIP"],         # Lista de roles

    # Metadados
    audio_duration=2.5,              # Duração em segundos
    timestamp=datetime.now()         # Momento da captura
)

# Uso
if voice_input.is_creator:
    print("Criador falou!")

if voice_input.confidence < 0.5:
    print("Transcrição com baixa confiança")

if "Admin" in voice_input.roles:
    print("Usuário é admin")
```

---

## 🔐 Sistema de Permissões

### Configurar Criador

```python
from voice import permission_manager

# Por username (primeira vez)
permission_manager.creator_username = "Leconcre"

# Ou por ID (mais seguro)
permission_manager.set_creator_id(123456789)
```

### Verificar Permissões

```python
async def on_voice(voice_input: VoiceInput):
    # Método 1: Campos diretos
    if voice_input.is_creator:
        # Comandos exclusivos do criador
        pass

    # Método 2: Funções auxiliares
    from voice import is_creator_speaking, has_role

    if is_creator_speaking(voice_input):
        print("Criador!")

    if has_role(voice_input, "Moderador"):
        print("Moderador!")
```

### Hierarquia

1. **Criador** (`is_creator=True`)
   - Definido por `creator_username` ou `set_creator_id()`
   - Maior nível de permissão

2. **Admin** (`is_admin=True`)
   - Tem permissão `administrator` no Discord
   - Ou é o dono do servidor

3. **Moderador**
   - Permissões: kick, ban, manage_messages
   - Verificar com `permission_manager.is_moderator(member)`

4. **Usuário normal**
   - Qualquer membro do servidor

---

## ⚙️ Configurações Avançadas

### Trocar Modelo Whisper

```python
from voice import listen_from_discord

# Rápido (menos preciso)
await listen_from_discord(vc, callback, model_size="tiny")

# Balanceado (RECOMENDADO)
await listen_from_discord(vc, callback, model_size="small")

# Preciso (mais lento)
await listen_from_discord(vc, callback, model_size="medium")

# Máximo (requer GPU)
await listen_from_discord(vc, callback, model_size="large-v3")
```

### Ajustar Sensibilidade VAD

```python
from voice.stt.vad import DiscordVAD

# Mais sensível (detecta voz baixa)
vad = DiscordVAD(energy_threshold=0.003)

# Menos sensível (ignora ruído)
vad = DiscordVAD(energy_threshold=0.01)
```

### GPU Acceleration

```python
from voice.stt.transcriber import AudioTranscriber

# Com CUDA (NVIDIA GPU)
transcriber = AudioTranscriber(
    model_size="medium",
    device="cuda",
    compute_type="float16"
)
```

---

## 🐛 Troubleshooting

### Erro: "No module named 'discord'"

**Causa:** py-cord não está instalado

**Solução:**
```bash
pip uninstall discord.py discord -y
pip install py-cord[voice] PyNaCl
```

### Erro: "No attribute 'sinks'"

**Causa:** Está usando discord.py ao invés de py-cord

**Solução:**
```bash
pip uninstall discord.py discord -y
pip install py-cord[voice]

# Verificar
python -c "import discord; print(discord.__version__)"
# Deve mostrar: 2.6.x (py-cord)
```

### Bot não captura áudio

**Verificações:**

1. **Permissões do bot no servidor:**
   - View Channel
   - Connect
   - Speak
   - Use Voice Activity (importante!)

2. **Verificar se está usando py-cord:**
   ```python
   import discord
   print(discord.__version__)  # Deve ser 2.6.x
   print(hasattr(discord, 'sinks'))  # Deve ser True
   ```

3. **Verificar se gravação iniciou:**
   ```python
   if voice_client.is_recording():
       print("✅ Gravando")
   else:
       print("❌ NÃO está gravando!")
   ```

4. **Logs:**
   - Procure por `"✅ ESCUTANDO canal:"`
   - Se não aparecer, há erro na inicialização

### Transcrição com erros

1. **Use modelo maior:**
   ```python
   model_size="medium"  # Ao invés de "small"
   ```

2. **Qualidade do microfone:**
   - Discord já processa áudio
   - Ruído pode afetar transcrição

3. **Idioma:**
   - Confirme que está em português (pt-BR)
   - Whisper detecta automaticamente, mas force se necessário

---

## 📖 Documentação Completa

### Arquivos de Referência

- **[GUIA_PY_CORD.md](GUIA_PY_CORD.md)** (este arquivo) - Guia principal
- **[eve_discord_bot.py](eve_discord_bot.py)** - Bot completo
- **[voice/stt/discord_listener.py](voice/stt/discord_listener.py)** - Implementação do Sink

### Estrutura de Arquivos

```
voice/
├── stt/
│   ├── discord_listener.py    ← VoiceRecordingSink (py-cord)
│   ├── models.py              ← VoiceInput
│   ├── user_tracker.py        ← Mapeia user_id → Member
│   ├── vad.py                 ← Voice Activity Detection
│   └── transcriber.py         ← faster-whisper
├── permissions.py             ← Sistema de permissões
└── discord_integration.py     ← listen_from_discord()
```

---

## 🎉 Checklist de Funcionamento

Use esta lista para verificar se tudo está funcionando:

- [ ] `pip list | grep py-cord` mostra py-cord instalado
- [ ] `python -c "import discord.sinks"` não dá erro
- [ ] FFmpeg instalado (`ffmpeg -version` funciona)
- [ ] Bot conecta ao Discord
- [ ] `!join` funciona (bot entra no canal)
- [ ] `!listen` mostra "✅ ESCUTANDO!"
- [ ] Ao falar, aparece log: `"🎤 Iniciando captura..."`
- [ ] Transcrição aparece: `"✅ Usuario: texto transcrito"`
- [ ] Bot responde (chat + voz)

Se todos os itens estão ✅, o sistema está funcionando!

---

## 🚀 Performance

### Comparação de Modelos

| Modelo | CPU (i7) | GPU (RTX 3060) | Precisão | Uso |
|--------|----------|----------------|----------|-----|
| tiny | ~1s | ~0.2s | 85% | Testes |
| **small** | **~3s** | **~0.5s** | **92%** | **Produção** |
| medium | ~8s | ~1.2s | 96% | Alta precisão |
| large-v3 | ~20s | ~3s | 98% | Máximo |

**Recomendação:** Use `small` para produção (bom balanço).

---

## 📝 Exemplo de Log Completo

```
[INFO] 📦 Módulo de voz EVE v1.0.0 carregado
[INFO]    Sample rate: 16000Hz
[INFO]    Whisper model: small
[INFO]    Discord STT: ✅ Disponível
[INFO] 🤖 BOT conectado como: EVE Bot (ID: 987654321)
[INFO] 💡 Use !listen para ativar escuta de voz!

> Usuário: !join
[INFO] Conectado ao canal: General

> Usuário: !listen
[INFO] ✅ VoiceRecordingSink inicializado (py-cord)
[INFO] Criando transcritor padrão (small, pt, cpu)...
[INFO] ✅ Modelo Whisper carregado!
[INFO] ✅ ESCUTANDO canal: General
[INFO]    Usuários no canal: ['Leconcre', 'User2']

> Leconcre (voz): "EVE, qual é a capital do Brasil?"

[INFO] 🎤 Iniciando captura de áudio: Leconcre (ID: 123456789)
[INFO] 📝 Processando 2.80s de áudio de: Leconcre
[INFO] Transcrição: 'EVE, qual é a capital do Brasil?' (confiança: 0.96)
[INFO] ✅ Leconcre [CREATOR]: EVE, qual é a capital do Brasil?
[INFO] 🤖 EVE: A capital do Brasil é Brasília.
[INFO] 🔊 Falando: A capital do Brasil é Brasília.
[INFO] ✅ Áudio reproduzido no Discord
```

---

## 🆘 Suporte

### Comandos de Debug

```python
# Verificar se é py-cord
import discord
print(discord.__version__)  # 2.6.x = py-cord
print(hasattr(discord, 'sinks'))  # True = py-cord

# Verificar gravação
if voice_client.is_recording():
    print("✅ Gravando")

# Testar Whisper
from voice.stt.transcriber import AudioTranscriber
t = AudioTranscriber(model_size="tiny")
# Deve carregar sem erro
```

### Recursos Úteis

- **Documentação py-cord:** https://docs.pycord.dev/
- **Whisper modelos:** https://github.com/SYSTRAN/faster-whisper
- **FFmpeg download:** https://ffmpeg.org/download.html

---

## ✅ Resumo

| Item | Detalhes |
|------|----------|
| **Biblioteca** | `py-cord[voice]` (NÃO discord.py) |
| **Por que py-cord?** | discord.py não recebe áudio |
| **Instalação** | `pip install py-cord[voice] PyNaCl faster-whisper` |
| **Comando principal** | `!listen` |
| **Sink usado** | `VoiceRecordingSink(discord.sinks.Sink)` |
| **Callback** | `write(data, user)` |
| **Identificação** | `user.id`, `user.name`, `user.roles` |
| **Transcrição** | faster-whisper (pt-BR) |
| **Modelo recomendado** | `small` |

---

**🎉 EVE agora OUVE de verdade usando py-cord!**
