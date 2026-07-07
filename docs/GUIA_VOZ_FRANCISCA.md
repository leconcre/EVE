# 🎤 Guia: EVE com Voz da Francisca

A EVE agora usa a voz **Francisca** (Edge TTS) como padrão!

## ✅ Configuração Atual

- **Voz:** Francisca (pt-BR-FranciscaNeural)
- **Engine:** Edge TTS (Microsoft)
- **Qualidade:** ⭐⭐⭐⭐⭐ (Neural, alta qualidade)
- **Status:** Funcionando ✅

## 🚀 Como Usar

### **Opção 1: Conversa Completa com EVE**

```bash
python eve_com_voz.py
```

Isso vai:
1. ✅ Carregar a EVE
2. ✅ Você digita perguntas
3. ✅ EVE responde (texto + áudio MP3)
4. ✅ Todos os áudios são salvos para você ouvir

**Exemplo:**
```
Você: Quem foi Albert Einstein?
EVE: [responde com texto e gera MP3]
💾 Áudio salvo: eve_resposta_1.mp3
```

### **Opção 2: Teste Rápido da Voz**

Crie `teste_francisca.py`:

```python
from voice import TextToSpeech

# Cria TTS com Francisca (já é o padrão)
tts = TextToSpeech(engine="edge")

# Testa
tts.synthesize(
    "Olá! Eu sou a EVE. Como posso ajudar você hoje?",
    save_to="teste_francisca.mp3",
    play=False
)

print("✅ Áudio salvo: teste_francisca.mp3")
```

Execute:
```bash
python teste_francisca.py
```

### **Opção 3: Uso Simplificado**

```python
from voice import speak

# Usa voz padrão (Francisca)
speak("Olá! Teste de voz.")
```

## 📝 Código para Integração

### Básico

```python
from voice import TextToSpeech

tts = TextToSpeech(engine="edge")
tts.synthesize("Seu texto aqui", save_to="audio.mp3", play=False)
```

### Com EVE

```python
from core.eve import Eve
from voice import TextToSpeech

eve = Eve()
tts = TextToSpeech(engine="edge")

# Pergunta
pergunta = "O que é inteligência artificial?"

# Processa
resposta = eve.generate_response(pergunta)
texto = resposta['text']

# Gera áudio
tts.synthesize(texto, save_to="resposta.mp3", play=False)
```

### Especificar Francisca Explicitamente

```python
from voice import TextToSpeech

# Modo explícito
tts = TextToSpeech(
    engine="edge",
    voice_model="pt-BR-FranciscaNeural"
)
```

## 🎯 Personalização da Voz

### Velocidade

```python
tts = TextToSpeech(engine="edge", rate=1.2)  # 20% mais rápido
tts = TextToSpeech(engine="edge", rate=0.8)  # 20% mais lento
```

### Volume

```python
tts = TextToSpeech(engine="edge", volume=1.5)  # 50% mais alto
tts = TextToSpeech(engine="edge", volume=0.7)  # 30% mais baixo
```

### Combinado

```python
tts = TextToSpeech(
    engine="edge",
    voice_model="pt-BR-FranciscaNeural",
    rate=1.1,     # 10% mais rápido
    volume=1.2    # 20% mais alto
)
```

## 🔧 Próximos Passos

### Para Usar Áudio Automaticamente (sem salvar MP3)

1. **Instale FFmpeg:**
   ```bash
   winget install FFmpeg
   ```

2. **Reinicie o terminal**

3. **Teste:**
   ```python
   from voice import speak
   speak("Teste com reprodução automática!", engine="edge")
   ```

### Para Ouvir com Voz (STT)

1. **Instale dependências:**
   ```bash
   pip install pyaudio faster-whisper
   ```

2. **Use o sistema completo:**
   ```python
   from voice import listen, speak

   texto = listen()  # Ouve sua voz
   speak(f"Você disse: {texto}", engine="edge")
   ```

## 📊 Comparação de Uso

| Modo | Requer FFmpeg | Reproduz Auto | Salva MP3 |
|------|---------------|---------------|-----------|
| Atual (save_to) | ❌ Não | ❌ Não | ✅ Sim |
| Com FFmpeg (play=True) | ✅ Sim | ✅ Sim | ⚠️ Opcional |
| Função speak() | ✅ Sim | ✅ Sim | ❌ Não |

## 💡 Dicas

### Organizar Áudios

```python
from pathlib import Path

# Cria pasta para áudios
pasta = Path("audios_eve")
pasta.mkdir(exist_ok=True)

# Salva organizado
tts.synthesize(
    "Resposta da EVE",
    save_to=pasta / "resposta_001.mp3",
    play=False
)
```

### Evitar Sobrescrever

```python
from datetime import datetime

# Nome único com timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
arquivo = f"eve_{timestamp}.mp3"

tts.synthesize("Texto", save_to=arquivo, play=False)
```

## ❓ FAQ

**Q: Preciso especificar "pt-BR-FranciscaNeural" sempre?**
R: Não! Francisca já é o padrão. Use apenas `TextToSpeech(engine="edge")`.

**Q: Como trocar para outra voz?**
R: `TextToSpeech(engine="edge", voice_model="pt-BR-ThalitaNeural")`

**Q: Por que o áudio não toca automaticamente?**
R: Precisa instalar FFmpeg. Enquanto isso, abra os MP3 manualmente.

**Q: Posso usar offline?**
R: Não. Edge TTS precisa de internet. Para offline, use pyttsx3 ou Piper.

## 🎉 Resumo

- ✅ **Voz configurada:** Francisca (Edge TTS)
- ✅ **Qualidade:** Excelente (neural)
- ✅ **Uso:** `python eve_com_voz.py`
- ⏭️ **Próximo passo:** Instalar FFmpeg para reprodução automática

---

**A EVE agora tem uma voz linda! 🎤✨**
