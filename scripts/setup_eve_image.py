# setup_eve_image.py - Configura imagem da EVE
"""
Execute este script para configurar a imagem da EVE corretamente
"""

import os
import shutil
from PIL import Image

print("🖼️ Configurando imagem da EVE...\n")

# Cria pasta assets se não existir
if not os.path.exists("assets"):
    os.makedirs("assets")
    print("✅ Pasta 'assets' criada")

# Procura a imagem
possible_names = ["eve_avatar.webp", "eve_image.webp", "eve.webp"]
source_image = None

for name in possible_names:
    if os.path.exists(name):
        source_image = name
        print(f"✅ Imagem encontrada: {name}")
        break

if source_image:
    try:
        # Converte para PNG (mais compatível)
        img = Image.open(source_image)
        
        # Salva em vários formatos e locais
        locations = [
            "eve_avatar.png",
            "assets/eve_avatar.png",
            "eve_avatar.webp",
            "assets/eve_avatar.webp"
        ]
        
        for loc in locations:
            if loc.endswith('.png'):
                img.save(loc, "PNG")
            else:
                img.save(loc, "WEBP")
            print(f"✅ Salvo: {loc}")
        
        print("\n✅ SUCESSO! Imagem configurada em múltiplos locais")
        print("\n🚀 Agora execute: python eve_gui_ultra.py")
        
    except Exception as e:
        print(f"\n❌ Erro ao processar imagem: {e}")
        print("💡 Tente instalar Pillow: pip install pillow")
else:
    print("❌ Imagem não encontrada!")
    print("\n💡 Certifique-se de que eve_avatar.webp está na pasta do projeto")
    print("   Locais procurados:")
    for name in possible_names:
        print(f"   - {name}")