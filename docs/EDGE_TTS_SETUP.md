# 🎯 Guia Rápido: Edge TTS

## ✅ Status Atual

- ✅ Edge TTS instalado e funcionando
- ✅ Voz **Francisca** testada com sucesso
- ⚠️ FFmpeg não instalado (necessário para integração completa)
- ⚠️ Algumas vozes podem ter nomes diferentes

## 🚀 Instalação em 2 Passos

### Passo 1: Instalar FFmpeg (ESSENCIAL)

```bash
# Windows
winget install FFmpeg

# Ou baixe manualmente:
# https://ffmpeg.org/download.html
```

**Depois de instalar, reinicie o terminal e verifique:**
```bash
ffmpeg -version
```

### Passo 2: Teste Funcionando

```bash
# Teste simples (gera MP3, não precisa FFmpeg)
python test_edge_simple.py

# Teste completo (depois de instalar FFmpeg)
python test_edge_tts.py
```

## 🎭 Vozes Disponíveis

Para listar TODAS as vozes realmente disponíveis:

```bash
python list_edge_voices.py
```

Isso vai mostrar os nomes **corretos** de todas as vozes.

## 📝 Uso Básico (Depois de Instalar FFmpeg)

### Teste Rápido

```python
from voice import speak

# Voz padrão (Francisca)
speak("Olá! Eu sou a EVE.")
```

### Escolher Voz Específica

```python
from voice import TextToSpeech

# Testa com voz específica
tts = TextToSpeech(engine="edge", voice_model="pt-BR-FranciscaNeural")
tts.synthesize("Teste de voz", play=True)
```

### Com EVE

```python
from core.eve import Eve
from voice import listen, speak, TextToSpeech

eve = Eve()

# Configura TTS com Edge
tts = TextToSpeech(engine="edge", voice_model="pt-BR-FranciscaNeural")

while True:
    # Ouve (quando instalar PyAudio)
    text = input("Você: ")  # Por enquanto, via teclado

    # Processa
    response = eve.generate_response(text)
    eve_text = response['text']

    print(f"EVE: {eve_text}")

    # Fala
    tts.synthesize(eve_text, play=True)
```

## ⚡ Solução Temporária (SEM FFmpeg)

Se não quiser instalar FFmpeg agora, você pode:

1. **Gerar MP3 e ouvir manualmente:**

```python
from voice.edge_tts_engine import EdgeTTSEngine

engine = EdgeTTSEngine(voice="pt-BR-FranciscaNeural")
audio_file = engine.synthesize("Teste")
print(f"Áudio salvo em: {audio_file}")
# Abra o arquivo .mp3 manualmente
```

2. **Usar pyttsx3 temporariamente:**

```bash
pip install pyttsx3
```

```python
from voice import speak
speak("Teste", engine="pyttsx3")
```

## 🔧 Troubleshooting

### ❌ "No audio was received"

Algumas vozes podem ter nomes ligeiramente diferentes. Execute:

```bash
python list_edge_voices.py
```

E use o nome **exato** mostrado (ex: `pt-BR-FranciscaNeural`).

### ❌ "FFmpeg não encontrado"

```bash
# Instale
winget install FFmpeg

# Reinicie o terminal
# Teste
ffmpeg -version
```

### ❌ Outras dependências faltando

Para usar o sistema COMPLETO de voz, instale:

```bash
pip install pyaudio faster-whisper sounddevice
```

Mas para testar só o TTS, apenas Edge TTS + FFmpeg são suficientes!

## 🎯 Próximos Passos

1. ✅ **Instale FFmpeg** (essencial)
2. ✅ **Liste vozes reais:** `python list_edge_voices.py`
3. ✅ **Teste vozes:** `python test_edge_simple.py`
4. ✅ **Escolha sua favorita** e configure
5. ⏭️ **Instale outras dependências** (PyAudio, Whisper) quando quiser o sistema completo

---

**Resumo: Edge TTS está funcionando! Só falta instalar FFmpeg para integração completa.** 🚀
