# setup_assets.py - Configuração de Assets (Avatar EVE e Backgrounds)
"""
Script para baixar/criar assets da interface gráfica
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import urllib.request

def create_assets_folder():
    """Cria pasta assets"""
    if not os.path.exists("assets"):
        os.makedirs("assets")
        print("✅ Pasta 'assets' criada")

def create_eve_avatar():
    """Cria avatar placeholder da EVE (roxo cyberpunk)"""
    # Avatar 200x200 de alta qualidade
    img = Image.new('RGB', (200, 200), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Círculo roxo gradiente
    for i in range(100):
        color_val = int(157 - (i * 0.5))  # Gradiente roxo
        draw.ellipse([i, i, 200-i, 200-i], fill=(color_val, 77, 237))
    
    # Adiciona "E" estilizado
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except Exception:
        font = ImageFont.load_default()
    
    # Texto centralizado
    text = "E"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (200 - text_width) // 2
    y = (200 - text_height) // 2 - 10
    
    draw.text((x, y), text, fill='#ffffff', font=font)
    
    # Salva
    img.save("assets/eve_avatar.png")
    print("✅ Avatar EVE criado: assets/eve_avatar.png")
    
    return img

def create_anime_background():
    """Cria background cyberpunk/anime"""
    # Background 1920x1080
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Gradiente vertical (azul escuro -> roxo escuro)
    for y in range(height):
        # Transição de #0a0a0f (topo) para #2d1b69 (baixo)
        r = int(10 + (y / height) * (45 - 10))
        g = int(10 + (y / height) * (27 - 10))
        b = int(15 + (y / height) * (105 - 15))
        
        draw.rectangle([0, y, width, y+1], fill=(r, g, b))
    
    # Adiciona "estrelas" (pontos brilhantes)
    import random
    for _ in range(200):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.randint(1, 3)
        brightness = random.randint(150, 255)
        draw.ellipse([x, y, x+size, y+size], fill=(brightness, brightness, brightness))
    
    # Linhas diagonais sutis (efeito cyber)
    for i in range(0, width, 100):
        draw.line([(i, 0), (i + height//2, height)], fill=(40, 40, 60), width=1)
    
    # Aplica blur suave
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    
    # Escurece um pouco
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.6)
    
    # Salva
    img.save("assets/bg_anime.jpg", quality=85)
    print("✅ Background criado: assets/bg_anime.jpg")
    
    return img

def create_user_avatar():
    """Cria avatar do usuário (azul)"""
    img = Image.new('RGB', (200, 200), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Círculo azul
    for i in range(100):
        color_val = int(30 + (i * 0.3))
        draw.ellipse([i, i, 200-i, 200-i], fill=(30, 58, color_val + 60))
    
    # Ícone usuário simplificado
    # Cabeça
    draw.ellipse([70, 60, 130, 120], fill='#ffffff')
    # Corpo
    draw.ellipse([50, 110, 150, 180], fill='#ffffff')
    
    img.save("assets/user_avatar.png")
    print("✅ Avatar usuário criado: assets/user_avatar.png")
    
    return img

def download_eve_image():
    """
    OPCIONAL: Baixa imagem real da EVE de Stellar Blade
    
    NOTA: Você pode substituir o placeholder pelo avatar real:
    1. Baixe uma imagem da EVE (Stellar Blade)
    2. Salve como: assets/eve_avatar.png
    3. Recomendado: 200x200px, fundo transparente
    """
    print("\n📝 NOTA: Para usar imagem real da EVE:")
    print("   1. Baixe uma imagem da EVE (Stellar Blade)")
    print("   2. Redimensione para 200x200px")
    print("   3. Salve como: assets/eve_avatar.png")
    print("   4. Reinicie a interface\n")

def create_all_assets():
    """Cria todos os assets"""
    print("🎨 Criando assets da interface...\n")
    
    create_assets_folder()
    create_eve_avatar()
    create_anime_background()
    create_user_avatar()
    download_eve_image()
    
    print("\n✅ CONCLUÍDO! Assets prontos em /assets/")
    print("   - eve_avatar.png (avatar EVE)")
    print("   - bg_anime.jpg (background)")
    print("   - user_avatar.png (seu avatar)")
    print("\n🚀 Execute: python eve_gui_full.py")

if __name__ == "__main__":
    create_all_assets()