# ✅ Checklist - Colocar EVE no Discord

## Você Já Fez:
- [x] Criar bot no Discord Developer Portal
- [x] Adicionar bot ao servidor

## Falta Fazer:

### 1. Copiar Token
- [ ] Ir em https://discord.com/developers/applications
- [ ] Clicar na aplicação EVE
- [ ] Ir em **Bot** (menu lateral)
- [ ] Clicar em **Reset Token**
- [ ] **Copiar** o token

### 2. Ativar Intents (IMPORTANTE!)
- [ ] Ainda em **Bot**, rolar até **Privileged Gateway Intents**
- [ ] Ativar: **Presence Intent**
- [ ] Ativar: **Server Members Intent**
- [ ] Ativar: **Message Content Intent**
- [ ] Clicar em **Save Changes**

### 3. Criar arquivo .env
- [ ] Criar arquivo chamado `.env` (sem extensão) na pasta do projeto
- [ ] Escrever dentro: `DISCORD_BOT_TOKEN=cole_token_aqui`
- [ ] Substituir `cole_token_aqui` pelo token copiado

**Atalho PowerShell:**
```powershell
notepad .env
```
Dentro do arquivo:
```
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5...seu_token_real_aqui
```

### 4. Instalar Dependências
```powershell
pip install discord.py[voice] PyNaCl python-dotenv
```

### 5. Verificar FFmpeg
```powershell
ffmpeg -version
```

Se der erro:
```powershell
winget install FFmpeg
```
**Depois reinicie o PowerShell!**

### 6. Iniciar Bot
```powershell
python eve_discord_bot.py
```

**Ou clique duas vezes em:** `iniciar_bot_discord.bat`

### 7. Testar no Discord
- [ ] Ir no seu servidor Discord
- [ ] Digitar: `!eve teste`
- [ ] EVE deve responder!

## 🎉 Sucesso!

Se EVE respondeu, está funcionando!

Para testar voz:
1. Entre num canal de voz
2. Digite: `!join`
3. Digite: `!eve olá`
4. EVE vai falar!

## ❌ Se Der Erro

### "DISCORD_BOT_TOKEN não encontrado"
→ Arquivo `.env` não existe ou está vazio
→ Solução: Crie o arquivo com o token

### "Privileged intent not enabled"
→ Não ativou os Intents
→ Solução: Discord Developer → Bot → Ative os 3 Intents → Save

### "discord não encontrado"
→ Não instalou as dependências
→ Solução: `pip install discord.py[voice] PyNaCl`

### "FFmpeg não encontrado"
→ Voz no Discord não vai funcionar
→ Solução: `winget install FFmpeg` + reiniciar terminal

## 📝 Resumo Ultra-Rápido

```powershell
# 1. Copie o token do bot

# 2. Crie .env
notepad .env
# Cole: DISCORD_BOT_TOKEN=seu_token

# 3. Instale
pip install discord.py[voice] PyNaCl python-dotenv
winget install FFmpeg

# 4. Inicie
python eve_discord_bot.py

# 5. Teste no Discord
# !eve olá
```

---

**Precisa de ajuda? Só falar!** 🚀
