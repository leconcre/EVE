# EVE - Assistente Virtual Inteligente

Assistente de IA pessoal com personalidade (inspirada na EVE de Stellar Blade),
que roda com modelos locais (Ollama) e nuvem (Groq), com GUI, CLI e bot de
Discord com voz.

## Estrutura

```
core/       Motor principal (Brain V2, router, contexto, personalidade)
engines/    Engines de modelo (Groq API)
memory/     Memória em camadas (short/long-term, preferências, cache)
skills/     Skills (calculadora, análise de logs, arquivos etc.)
voice/      TTS (Edge) e STT (Whisper) para o Discord
data/       Dados de runtime (memória, chats, flags) — fora do git
docs/       Documentação e guias de instalação
scripts/    Scripts utilitários (atalhos, instalação)
tests/      Testes unitários e scripts de teste manuais
```

## Como rodar

1. **Dependências**

   ```
   pip install -r requirements.txt
   ```

   Para o bot Discord com voz: `pip install -r requirements_voice_recv.txt`
   (e FFmpeg instalado no sistema).

2. **Configuração** — copie `.env.example` para `.env` e preencha:

   ```
   GROQ_API_KEY=...        # https://console.groq.com/keys
   DISCORD_BOT_TOKEN=...   # só para o bot Discord
   ```

3. **Ollama** (modelos locais) — instale em https://ollama.com e baixe:

   ```
   ollama pull llama3.1:8b
   ollama pull qwen2.5
   ollama pull qwen3-vl:8b
   ```

4. **Interfaces**

   | Interface | Comando |
   |-----------|---------|
   | GUI       | `python eve_gui.py` |
   | Terminal  | `python main.py` |
   | Discord   | `python eve_discord_bot.py` |

## Recursos

- **Híbrido nuvem/local**: chat tenta o Groq (rápido) e cai para o Ollama
  local automaticamente se a nuvem falhar. Código sempre via Groq 70B.
- **Streaming**: no terminal e na GUI, respostas do modelo local aparecem
  progressivamente enquanto são geradas.
- **Busca web**: Wikipedia → DuckDuckGo → Google → SearXNG, com regras
  anti-alucinação no prompt.
- **Memória em camadas**: curto/longo prazo, preferências e resumo de sessão.
- **Comandos do Discord**: `!eve`, `!falar`, `!join`, `!leave`, `!listen`,
  `!memoria` (ver/limpar memória), `!status` (saúde dos sistemas).
- **Feature flags** em `data/eve_features.json` — incluindo o roteamento
  por capabilities experimental (`ENABLE_CAPABILITY_ROUTING`), que escolhe
  o melhor modelo disponível por tarefa.

## Testes

```
python -m unittest discover -s tests -p "test_unit*.py" -v
python -m unittest tests.test_unit_fixes tests.test_new_features -v
```

## Segurança

- Chaves e tokens moram **apenas** no `.env` (ignorado pelo git).
- Dados pessoais (memória, chats) ficam em `data/` (ignorado pelo git).
