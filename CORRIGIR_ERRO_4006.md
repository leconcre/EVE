# 🔧 Corrigir Erro 4006 - Discord Voice

## ❌ Erro Encontrado

```
discord.errors.ConnectionClosed: Shard ID None WebSocket closed with 4006
```

**Significado:** O bot não tem permissões corretas para conectar ao voice.

---

## ✅ Solução em 3 Passos

### 1. Habilitar Intents no Discord Developer Portal

1. Acesse: https://discord.com/developers/applications
2. Selecione seu bot (EVE)
3. Vá em **Bot** (menu lateral)
4. Role até **Privileged Gateway Intents**
5. **ATIVE** estas opções:
   - ✅ **PRESENCE INTENT**
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**
6. Clique em **Save Changes**

![Intents](https://i.imgur.com/example.png)

---

### 2. Verificar Permissões do Bot no Servidor

O bot precisa destas permissões **no servidor Discord**:

#### Permissões Necessárias:
- ✅ **View Channels** (Ver Canais)
- ✅ **Send Messages** (Enviar Mensagens)
- ✅ **Read Message History** (Ler Histórico)
- ✅ **Connect** (Conectar a Voz) ⚠️ IMPORTANTE
- ✅ **Speak** (Falar em Voz) ⚠️ IMPORTANTE
- ✅ **Use Voice Activity** (Usar Atividade de Voz) ⚠️ IMPORTANTE

#### Como Verificar:

1. No Discord, clique com botão direito no bot
2. Vá em **Manage** (Gerenciar)
3. Verifique se tem as permissões acima
4. Se não tiver, adicione

---

### 3. Reinvitar o Bot com Permissões Corretas

Se ainda não funcionar, **reinvite** o bot com as permissões corretas:

#### URL de Convite:

```
https://discord.com/api/oauth2/authorize?client_id=SEU_CLIENT_ID&permissions=3165184&scope=bot
```

**Substitua `SEU_CLIENT_ID`** pelo ID do seu bot.

#### Como Obter o Client ID:

1. Acesse: https://discord.com/developers/applications
2. Selecione seu bot
3. Vá em **OAuth2** → **General**
4. Copie o **Client ID**

#### Permissões Incluídas (3165184):

- Send Messages
- Read Messages/View Channels
- Read Message History
- Connect (Voice)
- Speak (Voice)
- Use Voice Activity

---

## 🔄 Depois de Fazer as Mudanças

1. **Reinicie o bot:**
   ```bash
   # Pressione Ctrl+C para parar
   # Execute novamente:
   python eve_discord_bot.py
   ```

2. **Teste novamente:**
   ```
   !join
   !listen
   ```

---

## 📋 Checklist

- [ ] Intents habilitados no Developer Portal
  - [ ] PRESENCE INTENT
  - [ ] SERVER MEMBERS INTENT
  - [ ] MESSAGE CONTENT INTENT
- [ ] Permissões no servidor
  - [ ] View Channels
  - [ ] Send Messages
  - [ ] Connect (Voice)
  - [ ] Speak (Voice)
  - [ ] Use Voice Activity
- [ ] Bot reiniciado
- [ ] Testado com !join

---

## 🆘 Se Ainda Não Funcionar

### Verificar Código dos Intents

O código já foi atualizado com os intents corretos:

```python
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
```

### Logs para Verificar

Execute o bot e procure por:

```
INFO:discord.voice_client:Starting voice handshake...
INFO:discord.voice_client:Voice handshake complete.
```

Se aparecer:
```
ERROR:discord.voice_client:Failed to connect to voice...
discord.errors.ConnectionClosed: ... code=4006
```

= Ainda falta permissão!

---

## 🎯 Causas Comuns do Erro 4006

| Causa | Solução |
|-------|---------|
| Intents não habilitados | Habilitar no Developer Portal |
| Permissão "Connect" faltando | Adicionar no servidor |
| Permissão "Speak" faltando | Adicionar no servidor |
| Bot sem "Use Voice Activity" | Adicionar no servidor |
| Token inválido/expirado | Regenerar token |

---

## ✅ Teste Rápido

Depois de fazer as mudanças, teste com:

```bash
# No Discord:
!join

# Deve aparecer:
# ✅ Conectado ao canal: Geral
```

Se conectar SEM erros = RESOLVIDO! 🎉

---

**Documentação:** [GUIA_PY_CORD.md](GUIA_PY_CORD.md)
