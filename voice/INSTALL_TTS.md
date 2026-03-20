# 🔧 Guia de Instalação - Coqui TTS

Coqui TTS pode ser complicado de instalar no Windows. Este guia apresenta soluções.

## ❌ Problemas Comuns

### Erro 1: Microsoft Visual C++ Build Tools

```
error: Microsoft Visual C++ 14.0 or greater is required
```

**Solução:**
```bash
# Instale Visual Studio Build Tools
# https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Ou use versão pré-compilada (veja abaixo)
```

### Erro 2: espeak-ng não encontrado

```
ERROR: espeak-ng not found
```

**Solução (Windows):**
```bash
# Baixe e instale espeak-ng:
# https://github.com/espeak-ng/espeak-ng/releases

# Adicione ao PATH:
# C:\Program Files\eSpeak NG
```

### Erro 3: Conflito com PyTorch

```
ERROR: Cannot install TTS and torch
```

**Solução:**
```bash
# Instale PyTorch primeiro
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Depois instale TTS
pip install TTS
```

## ✅ Soluções Alternativas (RECOMENDADO)

### Opção 1: Use pyttsx3 (Mais Fácil)

**Vantagens:**
- ✅ Instala sem problemas
- ✅ Funciona offline
- ✅ Sem dependências complexas

**Instalação:**
```bash
pip install pyttsx3
```

**Uso:**
```python
from voice import speak
speak("Olá! Eu sou a EVE.", engine="pyttsx3")
```

### Opção 2: Use gTTS (Simples, mas Online)

**Vantagens:**
- ✅ Fácil de instalar
- ✅ Boa qualidade (Google TTS)

**Desvantagens:**
- ❌ Precisa de internet

**Instalação:**
```bash
pip install gtts
```

**Uso:**
```python
from voice import speak
speak("Olá!", engine="gtts")
```

### Opção 3: Use Piper (Melhor Qualidade Offline)

**Vantagens:**
- ✅ Excelente qualidade
- ✅ Funciona offline
- ✅ Voz em português muito boa

**Instalação (Windows):**
```bash
winget install rhasspy.piper
```

**Uso:**
```python
from voice import speak
speak("Olá!", engine="piper")
```

## 🚀 Instalação Forçada do Coqui TTS

Se você REALMENTE quer usar Coqui TTS, tente estas soluções:

### Método 1: Instalação Simplificada

```bash
# 1. Instale PyTorch primeiro
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 2. Instale apenas pacotes essenciais
pip install TTS --no-deps

# 3. Instale dependências manualmente
pip install numpy scipy librosa soundfile
pip install mecab-python3 unidic-lite
```

### Método 2: Versão Específica

```bash
# Versão mais antiga e estável
pip install TTS==0.13.0
```

### Método 3: Conda (Se Usar Anaconda)

```bash
conda create -n tts python=3.9
conda activate tts
conda install -c conda-forge tts
```

## 🎯 Recomendação Final

Para a EVE, recomendo usar **pyttsx3** inicialmente porque:

1. ✅ Instala sem problemas
2. ✅ Funciona imediatamente
3. ✅ Qualidade aceitável
4. ✅ Sem dependências complicadas

Depois, quando você receber a voz customizada da EVE, você pode:
- Usar Piper com modelo customizado
- Ou integrar sua própria engine TTS

## 📝 Teste Rápido

Depois de instalar qualquer engine, teste:

```python
# Teste pyttsx3
from voice import speak
speak("Testando pyttsx3", engine="pyttsx3")

# Teste gTTS (precisa internet)
speak("Testando gTTS", engine="gtts")

# Teste Piper (se instalou)
speak("Testando Piper", engine="piper")
```

## 🔍 Verificar Instalação

```python
# Verifica o que está disponível
from voice import get_info

info = get_info()
print(info)
```

## ❓ Ainda com Problemas?

Se continuar com erro ao instalar TTS, **não se preocupe!**

O módulo de voz funciona perfeitamente com as outras engines. Você pode:

1. Usar `pyttsx3` agora
2. Adicionar Coqui TTS depois (se resolver as dependências)
3. Ou esperar sua voz customizada e usar outra solução

O importante é que o **sistema está pronto e modular** - trocar a engine é fácil!
