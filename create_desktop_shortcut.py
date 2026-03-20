# create_desktop_shortcut.py - ATALHO ATUALIZADO PARA EVE DEFINITIVA
"""
Cria atalho na área de trabalho para EVE
ATUALIZADO: Aponta para eve_gui_ultra_final.py
"""

import os
import sys
import winshell
from win32com.client import Dispatch
from PIL import Image

print("\n" + "="*60)
print("🎨 CRIADOR DE ATALHO DA EVE - VERSÃO ATUALIZADA")
print("="*60)

# ═══════════════════════════════════════════════════════════════════
# PASSO 1: Converte imagem para ícone
# ═══════════════════════════════════════════════════════════════════

print("\n📸 Convertendo foto da EVE para ícone...")

# Procura imagem da EVE
image_paths = [
    "eve_avatar.webp",
    "eve_avatar.png",
    "assets/eve_avatar.webp",
    "assets/eve_avatar.png",
    "eve_icon.ico"
]

eve_image = None
icon_path = None

# Verifica se já existe .ico
if os.path.exists("eve_icon.ico"):
    icon_path = os.path.join(os.getcwd(), "eve_icon.ico")
    print(f"  ✓ Ícone existente encontrado: {icon_path}")
else:
    # Procura imagem para converter
    for path in image_paths:
        if os.path.exists(path):
            eve_image = path
            print(f"  ✓ Imagem encontrada: {path}")
            break

    if eve_image:
        try:
            # Converte para ICO
            img = Image.open(eve_image)
            
            # Redimensiona para tamanhos de ícone
            img = img.resize((256, 256), Image.Resampling.LANCZOS)
            
            # Converte para RGB se necessário
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Salva como ICO
            icon_path = os.path.join(os.getcwd(), "eve_icon.ico")
            img.save(icon_path, format='ICO', sizes=[
                (256, 256), (128, 128), (64, 64), (32, 32), (16, 16)
            ])
            
            print(f"  ✓ Ícone criado: eve_icon.ico")
        except Exception as e:
            print(f"  ⚠️ Erro ao criar ícone: {e}")
            print("  ℹ️ Usando ícone padrão do Python")
            icon_path = None
    else:
        print("  ⚠️ Imagem da EVE não encontrada")
        print("  ℹ️ Usando ícone padrão do Python")

# ═══════════════════════════════════════════════════════════════════
# PASSO 2: Cria o atalho
# ═══════════════════════════════════════════════════════════════════

print("\n🔗 Criando atalho na área de trabalho...")

try:
    # Caminho da área de trabalho
    desktop = winshell.desktop()
    
    # ✅ ATUALIZADO: Aponta para eve_gui_DEFINITIVA.py
    script_path = os.path.join(os.getcwd(), "eve_gui_ultra_final.py")
    
    # Verifica se o arquivo existe
    if not os.path.exists(script_path):
        print(f"\n❌ ERRO: eve_gui_ultra_final.py não encontrado!")
        print(f"   Procurado em: {script_path}")
        print("\n💡 SOLUÇÃO:")
        print("   1. Certifique-se de que eve_gui_ultra_final.py está na pasta")
        print("   2. Ou execute este script dentro da pasta 'EVE - AI'")
        input("\nPressione Enter para sair...")
        sys.exit(1)
    
    # Caminho do Python
    python_exe = sys.executable
    
    # Caminho do atalho
    shortcut_path = os.path.join(desktop, "EVE - Stellar Blade AI.lnk")
    
    # Cria o atalho
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    
    # Configurações do atalho
    shortcut.Targetpath = python_exe
    shortcut.Arguments = f'"{script_path}"'
    shortcut.WorkingDirectory = os.getcwd()
    shortcut.Description = "EVE - Stellar Blade AI Assistant (Versão Completa com Groq)"
    
    # Define o ícone (se disponível)
    if icon_path and os.path.exists(icon_path):
        shortcut.IconLocation = icon_path
        print(f"  ✓ Ícone personalizado aplicado")
    else:
        # Usa ícone do Python como fallback
        shortcut.IconLocation = python_exe
        print(f"  ℹ️ Usando ícone padrão do Python")
    
    # Salva o atalho
    shortcut.save()
    
    print(f"\n✅ SUCESSO!")
    print(f"\n📁 Atalho criado em:")
    print(f"   {shortcut_path}")
    print(f"\n🎯 Executa:")
    print(f"   {script_path}")
    print(f"\n🖼️ Ícone:")
    if icon_path:
        print(f"   {icon_path}")
    else:
        print(f"   Padrão do Python")
    
    print("\n🎯 Para usar:")
    print("   1. Vá para a área de trabalho")
    print("   2. Clique duas vezes no atalho 'EVE - Stellar Blade AI'")
    print("   3. Pronto! ⚡")
    
    print("\n💡 DICA:")
    print("   Se quiser mudar o ícone depois:")
    print("   1. Botão direito no atalho → Propriedades")
    print("   2. Clique 'Alterar Ícone'")
    print("   3. Navegue até eve_icon.ico")

except Exception as e:
    print(f"\n❌ ERRO ao criar atalho: {e}")
    print("\n💡 SOLUÇÃO ALTERNATIVA:")
    print("   Instale as dependências:")
    print("   pip install pywin32 winshell pillow")
    print("\n   Ou crie o atalho manualmente:")
    print("   1. Botão direito na área de trabalho → Novo → Atalho")
    print(f"   2. Digite: {python_exe} {script_path}")
    print("   3. Clique 'Avançar' → Nomeie 'EVE - Stellar Blade AI'")

print("\n" + "="*60 + "\n")
input("Pressione Enter para sair...")