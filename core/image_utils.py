# core/image_utils.py
import os
import logging
from PIL import Image
from typing import Optional, Tuple

logger = logging.getLogger("image_utils")
logger.setLevel(logging.INFO)

# Configurações otimizadas
MAX_IMAGE_SIZE = (1280, 1280)  # Tamanho máximo (melhor qualidade)
MAX_FILE_SIZE_MB = 4  # Máximo 4MB
COMPRESSION_QUALITY = 85  # Qualidade JPEG


def compress_image_for_analysis(
    image_path: str,
    output_path: Optional[str] = None,
    max_size: Tuple[int, int] = MAX_IMAGE_SIZE,
    quality: int = COMPRESSION_QUALITY
) -> str:
    """
    Comprime imagem para análise mais rápida mantendo boa qualidade.
    
    Args:
        image_path: Caminho da imagem original
        output_path: Caminho de saída (opcional, usa temp se None)
        max_size: Tamanho máximo (width, height)
        quality: Qualidade JPEG (1-100)
        
    Returns:
        Caminho da imagem comprimida
    """
    try:
        # Verifica tamanho do arquivo
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        
        if file_size_mb <= MAX_FILE_SIZE_MB:
            logger.info(f"Imagem OK ({file_size_mb:.2f} MB) - sem compressão necessária")
            return image_path
        
        logger.info(f"Comprimindo imagem de {file_size_mb:.2f} MB...")
        
        # Abre imagem
        with Image.open(image_path) as img:
            # Converte para RGB se necessário
            if img.mode in ('RGBA', 'P', 'LA'):
                # Cria fundo branco para transparência
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])  # Alpha channel
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Redimensiona mantendo aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Define path de saída
            if output_path is None:
                name, ext = os.path.splitext(image_path)
                output_path = f"{name}_compressed.jpg"
            
            # Salva comprimido
            img.save(output_path, "JPEG", quality=quality, optimize=True)
            
            new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"✅ Comprimido: {file_size_mb:.2f} MB → {new_size_mb:.2f} MB ({img.size[0]}x{img.size[1]})")
            
            return output_path
            
    except Exception as e:
        logger.error(f"Erro ao comprimir: {e}")
        return image_path  # Retorna original em caso de erro


def get_image_info(image_path: str) -> dict:
    """
    Retorna informações sobre a imagem.
    
    Returns:
        Dict com width, height, format, size_mb, mode
    """
    try:
        with Image.open(image_path) as img:
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format or "UNKNOWN",
                "mode": img.mode,
                "size_mb": os.path.getsize(image_path) / (1024 * 1024),
                "aspect_ratio": f"{img.width}:{img.height}"
            }
    except Exception as e:
        logger.error(f"Erro ao obter info: {e}")
        return {}


def should_compress(image_path: str) -> bool:
    """
    Verifica se a imagem deve ser comprimida.
    
    Returns:
        True se deve comprimir
    """
    try:
        info = get_image_info(image_path)
        
        # Verifica tamanho do arquivo
        if info.get("size_mb", 0) > MAX_FILE_SIZE_MB:
            return True
        
        # Verifica dimensões
        width = info.get("width", 0)
        height = info.get("height", 0)
        
        if width > MAX_IMAGE_SIZE[0] or height > MAX_IMAGE_SIZE[1]:
            return True
        
        return False
        
    except Exception:
        return False


def validate_image(image_path: str) -> Tuple[bool, str]:
    """
    Valida se a imagem pode ser processada.
    
    Returns:
        (is_valid, error_message)
    """
    # Verifica se arquivo existe
    if not os.path.isfile(image_path):
        return False, "Arquivo não encontrado"
    
    # Verifica extensão
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
    if not image_path.lower().endswith(valid_extensions):
        return False, f"Formato não suportado. Use: {', '.join(valid_extensions)}"
    
    # Tenta abrir
    try:
        with Image.open(image_path) as img:
            # Verifica se não está corrompida
            img.verify()
        return True, "OK"
    except Exception as e:
        return False, f"Imagem corrompida: {str(e)}"


def optimize_for_ocr(image_path: str, output_path: Optional[str] = None) -> str:
    """
    Otimiza imagem para OCR (reconhecimento de texto).
    Aumenta contraste e converte para escala de cinza.
    
    Args:
        image_path: Caminho da imagem
        output_path: Caminho de saída (opcional)
        
    Returns:
        Caminho da imagem otimizada
    """
    try:
        from PIL import ImageEnhance
        
        with Image.open(image_path) as img:
            # Converte para escala de cinza
            img = img.convert('L')
            
            # Aumenta contraste
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            # Define path de saída
            if output_path is None:
                name, ext = os.path.splitext(image_path)
                output_path = f"{name}_ocr.jpg"
            
            # Salva
            img.save(output_path, "JPEG", quality=95)
            logger.info(f"Imagem otimizada para OCR: {output_path}")
            
            return output_path
            
    except Exception as e:
        logger.error(f"Erro ao otimizar para OCR: {e}")
        return image_path