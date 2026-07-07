# 🎧 Sistema de Escuta de Voz do Discord - EVE

Sistema completo de captura, identificação e transcrição de voz em tempo real para Discord.

## 📋 Índice

- [Características](#características)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Uso Básico](#uso-básico)
- [Uso Avançado](#uso-avançado)
- [Arquitetura](#arquitetura)
- [Sistema de Permissões](#sistema-de-permissões)
- [Exemplos de Código](#exemplos-de-código)
- [Troubleshooting](#troubleshooting)

## ✨ Características

### ✅ Implementado

- ✅ **Captura de áudio por usuário**: Cada usuário tem seu próprio stream de áudio
- ✅ **Identificação automática**: Sistema identifica quem está falando via Discord ID
- ✅ **Transcrição em português**: Usa faster-whisper otimizado para pt-BR
- ✅ **Detecção de voz (VAD)**: Filtra silêncio e ruído automaticamente
- ✅ **Sistema de permissões**: Reconhece criador, admins e moderadores
- ✅ **Arquitetura modular**: Componentes separados e reutilizáveis
- ✅ **Pronto para produção**: Tratamento robusto de erros e logging

### 🎯 Dados Retornados

Para cada fala detectada, o sistema retorna:

```python
VoiceInput(
    user_id=123456789,           # ID do Discord
    username="Leconcre",          # Nome de exibição
    text="Olá EVE, como vai?",   # Texto transcrito
    confidence=0.95,              # Confiança da transcrição (0-1)
    timestamp=datetime.now(),     # Momento da fala
    is_creator=True,              # Se é o criador do bot
    is_admin=True,                # Se é admin do servidor
    roles=["Admin", "Founder"],  # Roles do usuário
    audio_duration=2.5,           # Duração do áudio em segundos
    language="pt"                 # Idioma detectado
)
```

## 🔧 Requisitos

### Software Necessário

- **Python 3.9+**
- **FFmpeg** (para processamento de áudio)
- **CUDA** (opcional, para GPU acceleration)

### Dependências Python

```bash
# Discord
discord.py[voice]>=2.3.0
PyNaCl>=1.5.0

# Speech-to-Text
faster-whisper>=0.9.0

# Processamento de áudio
numpy>=1.24.0

# Utilitários
python-dotenv>=1.0.0
```

## 📦 Instalação

### 1. Instalar FFmpeg

#### Windows
```powershell
# Usando Chocolatey
choco install ffmpeg

# Ou baixe de: https://ffmpeg.org/download.html
# Adicione ao PATH do sistema
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

### 2. Instalar Dependências Python

```bash
# Navegue até o diretório do projeto
cd "C:\Users\lucas\Desktop\EVE - AI"

# Instale as dependências
pip install discord.py[voice] PyNaCl faster-whisper numpy python-dotenv
```

### 3. Verificar Instalação

```bash
# Teste o FFmpeg
ffmpeg -version

# Teste o import do Python
python -c "from faster_whisper import WhisperModel; print('✅ OK')"
```

## 🚀 Uso Básico

### 1. Iniciar o Bot

```bash
python eve_discord_bot.py
```

### 2. Comandos no Discord

```
!join          # EVE entra no seu canal de voz
!listen        # EVE começa a ouvir e transcrever
!stop_listen   # EVE para de ouvir
!leave         # EVE sai do canal
!eve [texto]   # Enviar comando de texto (modo antigo)
```

### 3. Fluxo de Uso

1. **Entre em um canal de voz no Discord**
2. **No chat, digite:** `!listen`
3. **EVE responderá:** "✅ Sistema de escuta ativado!"
4. **Fale normalmente no canal de voz**
5. **EVE vai:**
   - Detectar sua voz
   - Transcrever o que você disse
   - Processar com a IA
   - Responder no chat
   - Falar a resposta em voz

### 4. Exemplo Real

```
Você (voz): "EVE, qual é a capital do Brasil?"

[Bot transcrevendo...]

EVE (chat): 🤖 A capital do Brasil é Brasília.
EVE (voz): "A capital do Brasil é Brasília."
```

## 🎓 Uso Avançado

### Programático - Usar o Sistema no Seu Código

```python
from voice import listen_from_discord, VoiceInput

# Callback quando alguém fala
async def on_voice(voice_input: VoiceInput):
    # Verificar permissões
    if voice_input.is_creator:
        print(f"[CREATOR] {voice_input.username}: {voice_input.text}")
    elif voice_input.is_admin:
        print(f"[ADMIN] {voice_input.username}: {voice_input.text}")
    else:
        print(f"[USER] {voice_input.username}: {voice_input.text}")

    # Processar comando
    if "pare" in voice_input.text.lower():
        print("Comando de parada recebido!")

    # Verificar confiança
    if voice_input.confidence < 0.5:
        print("⚠️ Transcrição com baixa confiança")

# Iniciar escuta
listener = await listen_from_discord(
    voice_client,
    on_transcription=on_voice,
    model_size="small"  # ou "medium" para melhor precisão
)
```

### Verificar Permissões

```python
from voice import is_creator_speaking, is_admin_speaking, has_role

async def on_voice(voice_input: VoiceInput):
    # Método 1: Usar campos do VoiceInput
    if voice_input.is_creator:
        print("Comando do criador!")

    # Método 2: Usar funções auxiliares
    if is_creator_speaking(voice_input):
        print("Criador falou!")

    if is_admin_speaking(voice_input):
        print("Admin falou!")

    # Verificar role específica
    if has_role(voice_input, "Moderador"):
        print("Moderador falou!")
```

### Configurar o Criador

```python
from voice import permission_manager

# Definir o criador por username (primeira vez)
permission_manager.creator_username = "Leconcre"

# Ou definir diretamente por ID
permission_manager.set_creator_id(123456789)
```

## 🏗️ Arquitetura

### Estrutura de Pastas

```
voice/
├── __init__.py                    # API principal
├── config.py                      # Configurações
├── permissions.py                 # Sistema de permissões
├── discord_integration.py         # Função listen_from_discord()
│
├── stt/                          # Speech-to-Text
│   ├── __init__.py
│   ├── models.py                 # VoiceInput, AudioChunk
│   ├── discord_listener.py       # Captura por usuário
│   ├── user_tracker.py           # Mapeamento user_id → Member
│   ├── vad.py                    # Voice Activity Detection
│   └── transcriber.py            # faster-whisper integration
│
└── tts/                          # Text-to-Speech (já existente)
    └── ...
```

### Fluxo de Dados

```
1. Discord Audio Stream (48kHz, stereo, PCM)
   ↓
2. CustomSink (separa por user_id)
   ↓
3. DiscordVAD (detecta voz vs silêncio)
   ↓
4. Buffer de áudio (acumula até silêncio)
   ↓
5. AudioTranscriber (faster-whisper)
   ↓
6. UserTracker (mapeia ID → Member)
   ↓
7. PermissionManager (identifica criador/admin)
   ↓
8. VoiceInput (estrutura final)
   ↓
9. Callback do usuário (on_transcription)
```

### Componentes Principais

#### 1. DiscordVoiceListener
Orquestra todo o sistema de escuta.

```python
class DiscordVoiceListener:
    - start_listening(voice_client)
    - stop_listening()
    - _on_audio_chunk(chunk)
```

#### 2. CustomSink
Captura áudio separado por usuário.

```python
class CustomSink(discord.sinks.Sink):
    - write(data, user_id)  # Chamado pelo Discord
    - _process_user_audio(user_id)
```

#### 3. AudioTranscriber
Converte áudio em texto usando Whisper.

```python
class AudioTranscriber:
    - transcribe(audio_data) → dict
    - convert_discord_audio(bytes) → numpy
```

#### 4. UserTracker
Mantém mapeamento de IDs para Members.

```python
class UserTracker:
    - add_user(member)
    - get_user(user_id) → Member
    - update_from_channel(channel)
```

#### 5. PermissionManager
Identifica criador e admins.

```python
class PermissionManager:
    - get_permissions(member) → UserPermissions
    - is_creator(member) → bool
    - is_admin(member) → bool
```

## 🔐 Sistema de Permissões

### Configuração

Por padrão, o sistema identifica o criador pelo username **"Leconcre"**.

#### Personalizar o Criador

```python
# Em eve_discord_bot.py ou seu código
from voice import permission_manager

# Definir por username
permission_manager.creator_username = "SeuUsername"

# Ou definir diretamente por ID (mais seguro)
permission_manager.set_creator_id(123456789012345)
```

### Níveis de Permissão

#### 1. Criador (Creator)
- Identificado por `user_id` ou `username`
- `voice_input.is_creator == True`
- Maior nível de autoridade

#### 2. Administrador (Admin)
- Tem permissão `administrator` no servidor
- Ou é o dono do servidor
- `voice_input.is_admin == True`

#### 3. Moderador (Moderator)
- Tem permissões: kick, ban, ou manage_messages
- Pode ser verificado com `permission_manager.is_moderator(member)`

#### 4. Usuário (User)
- Qualquer outro membro do servidor

### Uso no Código

```python
async def on_voice(voice_input: VoiceInput):
    if voice_input.is_creator:
        # Comandos exclusivos do criador
        if "desligar" in voice_input.text:
            await shutdown_bot()

    elif voice_input.is_admin:
        # Comandos de admin
        if "silenciar" in voice_input.text:
            await mute_user()

    else:
        # Comandos normais
        process_normal_command(voice_input.text)
```

## 💻 Exemplos de Código

### Exemplo 1: Bot Simples que Responde a Comandos de Voz

```python
from voice import listen_from_discord, VoiceInput

async def processar_comando(voice_input: VoiceInput):
    texto = voice_input.text.lower()

    # Comandos específicos do criador
    if voice_input.is_creator:
        if "desligar" in texto:
            print(f"[CREATOR] Comando de desligamento recebido")
            await bot.close()
            return

    # Comandos gerais
    if "olá" in texto or "oi" in texto:
        print(f"{voice_input.username} disse olá!")

    elif "hora" in texto:
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M")
        print(f"São {hora}")

    print(f"Confiança: {voice_input.confidence:.2%}")

# Iniciar
await listen_from_discord(voice_client, processar_comando)
```

### Exemplo 2: Sistema de Logs com Identificação

```python
import json
from datetime import datetime
from voice import listen_from_discord, VoiceInput

logs = []

async def registrar_fala(voice_input: VoiceInput):
    log_entry = {
        "timestamp": voice_input.timestamp.isoformat(),
        "user_id": voice_input.user_id,
        "username": voice_input.username,
        "text": voice_input.text,
        "is_creator": voice_input.is_creator,
        "is_admin": voice_input.is_admin,
        "roles": voice_input.roles,
        "confidence": voice_input.confidence
    }

    logs.append(log_entry)

    # Salvar em arquivo
    with open("voice_logs.json", "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    print(f"📝 Registrado: {voice_input}")

await listen_from_discord(voice_client, registrar_fala)
```

### Exemplo 3: Filtrar por Roles

```python
from voice import listen_from_discord, has_role

async def processar_por_role(voice_input: VoiceInput):
    if has_role(voice_input, "VIP"):
        print(f"[VIP] {voice_input.username}: {voice_input.text}")
        # Processar com prioridade

    elif has_role(voice_input, "Moderador"):
        print(f"[MOD] {voice_input.username}: {voice_input.text}")
        # Comandos de moderação

    else:
        print(f"[USER] {voice_input.username}: {voice_input.text}")
        # Processamento normal
```

### Exemplo 4: Integração Completa com EVE

```python
# eve_discord_bot.py (já implementado)

from core.eve import Eve
from voice import listen_from_discord, VoiceInput

eve = Eve()

async def on_user_spoke(voice_input: VoiceInput):
    # Log
    creator_tag = " [CREATOR]" if voice_input.is_creator else ""
    print(f"🎤 {voice_input.username}{creator_tag}: {voice_input.text}")

    # Processa com EVE
    response = eve.generate_response(voice_input.text)
    response_text = response.get('text', '')

    if response_text:
        print(f"🤖 EVE: {response_text}")

        # Responder em voz (TTS)
        await speak_in_voice_channel(response_text)

# Comando para ativar
@bot.command()
async def listen(ctx):
    await listen_from_discord(
        ctx.voice_client,
        on_transcription=on_user_spoke,
        model_size="small"
    )
```

## 🐛 Troubleshooting

### Erro: "faster-whisper não instalado"

```bash
pip install faster-whisper
```

### Erro: "discord.sinks não encontrado"

```bash
pip install --upgrade discord.py[voice]
pip install PyNaCl
```

### Erro: "FFmpeg not found"

**Windows:**
1. Baixe FFmpeg: https://ffmpeg.org/download.html
2. Extraia para `C:\ffmpeg`
3. Adicione `C:\ffmpeg\bin` ao PATH
4. Reinicie o terminal

**Linux:**
```bash
sudo apt install ffmpeg
```

### Áudio não está sendo capturado

1. **Verifique se o bot tem permissões no servidor:**
   - View Channel
   - Connect
   - Speak
   - Use Voice Activity

2. **Verifique se está conectado:**
   ```python
   if ctx.voice_client and ctx.voice_client.is_connected():
       print("✅ Conectado")
   ```

3. **Verifique os logs:**
   - Procure por mensagens de erro no console
   - Use `logging.DEBUG` para mais detalhes

### Transcrição com erros

1. **Use modelo maior:**
   ```python
   await listen_from_discord(vc, callback, model_size="medium")
   ```

2. **Ajuste o VAD:**
   ```python
   from voice.stt.vad import DiscordVAD
   vad = DiscordVAD(energy_threshold=0.003)  # Mais sensível
   ```

3. **Verifique qualidade do áudio:**
   - Microfone com ruído pode afetar transcrição
   - Discord já faz algum processamento

### Bot não identifica o criador

```python
from voice import permission_manager

# Verificar configuração
print(f"Criador configurado: {permission_manager.creator_username}")

# Definir manualmente
permission_manager.set_creator_id(SEU_USER_ID)
```

Para obter seu user ID no Discord:
1. Ative o Modo Desenvolvedor (Configurações → Avançado)
2. Clique com botão direito no seu nome
3. "Copiar ID"

## 📊 Performance

### Tamanhos de Modelo Whisper

| Modelo | VRAM | Velocidade | Precisão |
|--------|------|-----------|----------|
| tiny   | ~1GB | Muito rápida | Boa |
| small  | ~2GB | Rápida | Muito boa |
| medium | ~5GB | Média | Excelente |
| large-v3 | ~10GB | Lenta | Máxima |

**Recomendação:** Use `small` para produção. Use `medium` se tiver GPU dedicada.

### Otimizações

```python
# CPU (padrão)
transcriber = AudioTranscriber(
    model_size="small",
    device="cpu",
    compute_type="int8"
)

# GPU (NVIDIA)
transcriber = AudioTranscriber(
    model_size="medium",
    device="cuda",
    compute_type="float16"
)
```

## 📝 Notas Finais

- ✅ Sistema totalmente funcional e pronto para produção
- ✅ Identificação por Discord ID (não biometria)
- ✅ Suporta múltiplos usuários simultâneos
- ✅ Tratamento robusto de erros
- ✅ Logging completo
- ✅ Modular e extensível

## 🆘 Suporte

Em caso de problemas:

1. Verifique os logs do bot
2. Consulte a seção [Troubleshooting](#troubleshooting)
3. Verifique se todas as dependências estão instaladas
4. Teste com `!join` antes de usar `!listen`

## 📄 Licença

Parte do projeto EVE AI.
