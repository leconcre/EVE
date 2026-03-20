# core/image_reader.py
import os
import logging
from PIL import Image
from collections import Counter
from typing import Dict, Optional, List, Tuple

# Dependências opcionais
try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    TESSERACT_AVAILABLE = False

logger = logging.getLogger("image_reader")
logger.setLevel(logging.INFO)

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]


class ImageReader:
    """
    Classe otimizada para análise de imagens.
    Suporta: informações básicas, OCR, cores dominantes, detecção de padrões.
    """

    def __init__(self):
        self.cv_available = CV_AVAILABLE
        self.ocr_available = TESSERACT_AVAILABLE
        
        if not CV_AVAILABLE:
            logger.warning("OpenCV não disponível. Funcionalidades limitadas.")
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract não disponível. OCR desabilitado.")

    def is_image(self, file_path: str) -> bool:
        """Verifica se o arquivo é uma imagem válida"""
        return os.path.isfile(file_path) and any(
            file_path.lower().endswith(ext) for ext in IMAGE_EXTENSIONS
        )

    def get_image_info(self, file_path: str) -> Dict[str, any]:
        """
        Retorna informações básicas da imagem.
        
        Returns:
            Dict com: width, height, format, mode, size_kb, aspect_ratio
        """
        if not os.path.isfile(file_path):
            return {"error": "Arquivo não encontrado"}
        
        try:
            with Image.open(file_path) as img:
                size_kb = os.path.getsize(file_path) / 1024
                aspect = img.width / img.height if img.height > 0 else 0
                
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format or "UNKNOWN",
                    "mode": img.mode,
                    "size_kb": round(size_kb, 2),
                    "aspect_ratio": f"{img.width}:{img.height}",
                    "is_landscape": img.width > img.height,
                    "megapixels": round((img.width * img.height) / 1_000_000, 2)
                }
        except Exception as e:
            logger.error(f"Erro ao obter info: {e}")
            return {"error": str(e)}

    def read_image(self, file_path: str) -> Image.Image:
        """Carrega imagem usando PIL"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        return Image.open(file_path)

    def extract_text(self, file_path: str, lang: str = 'por+eng') -> str:
        """
        OCR - Extrai texto da imagem.
        
        Args:
            file_path: Caminho da imagem
            lang: Idiomas (por+eng = português + inglês)
            
        Returns:
            Texto extraído ou mensagem de erro
        """
        if not TESSERACT_AVAILABLE:
            return "[OCR indisponível - pytesseract não instalado]"
        
        try:
            if CV_AVAILABLE:
                # Usa OpenCV para pré-processamento (melhor OCR)
                img = cv2.imread(file_path)
                if img is None:
                    raise ValueError(f"Falha ao carregar: {file_path}")
                
                # Converte para escala de cinza
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Aplica threshold para melhorar contraste
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # OCR
                text = pytesseract.image_to_string(thresh, lang=lang)
            else:
                # Usa PIL diretamente
                pil_img = Image.open(file_path)
                text = pytesseract.image_to_string(pil_img, lang=lang)
            
            text = text.strip()
            return text if text else "[Nenhum texto detectado]"
            
        except Exception as e:
            logger.error(f"Erro OCR: {e}")
            return f"[Erro OCR: {str(e)}]"

    def get_dominant_colors(self, file_path: str, top_k: int = 5) -> List[Tuple[str, int]]:
        """
        Retorna as cores dominantes da imagem.
        
        Args:
            file_path: Caminho da imagem
            top_k: Número de cores a retornar
            
        Returns:
            Lista de tuplas (cor_rgb, contagem)
        """
        if not CV_AVAILABLE:
            return [("OpenCV não disponível", 0)]
        
        try:
            img = cv2.imread(file_path)
            if img is None:
                raise ValueError(f"Falha ao carregar: {file_path}")
            
            # Converte BGR para RGB
            arr = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Redimensiona para análise mais rápida
            small = cv2.resize(arr, (100, 100), interpolation=cv2.INTER_AREA)
            pixels = small.reshape(-1, 3)
            
            # Conta cores
            counts = Counter(tuple(p) for p in pixels)
            
            # Retorna top K
            top_colors = counts.most_common(top_k)
            return [(f"RGB{c[0]}", c[1]) for c in top_colors]
            
        except Exception as e:
            logger.error(f"Erro ao extrair cores: {e}")
            return [(f"Erro: {str(e)}", 0)]

    def detect_screenshot_type(self, file_path: str) -> str:
        """
        Tenta detectar o tipo de screenshot (jogo, aplicativo, web, etc).
        
        Returns:
            Tipo detectado
        """
        try:
            info = self.get_image_info(file_path)
            
            # Screenshots de jogos geralmente são widescreen
            if info.get("is_landscape"):
                width = info.get("width", 0)
                height = info.get("height", 0)
                
                # Resoluções comuns de jogos
                if (width, height) in [(1920, 1080), (2560, 1440), (3840, 2160)]:
                    return "Possível screenshot de jogo (resolução padrão)"
                elif width / height > 1.7:
                    return "Tela widescreen (provável jogo ou aplicativo)"
            
            # Screenshots de celular são portrait
            if not info.get("is_landscape"):
                return "Tela portrait (possível celular)"
            
            return "Screenshot genérico"
            
        except Exception:
            return "Tipo desconhecido"

    def analyze_image(
        self, 
        file_path: str, 
        include_ocr: bool = False,
        include_colors: bool = False
    ) -> str:
        """
        Gera análise completa da imagem em formato legível.
        
        Args:
            file_path: Caminho da imagem
            include_ocr: Se deve incluir OCR
            include_colors: Se deve incluir análise de cores
            
        Returns:
            String com análise formatada
        """
        if not os.path.isfile(file_path):
            return f"❌ Arquivo não encontrado: {file_path}"
        
        parts = []
        parts.append(f"📸 Analisando: {os.path.basename(file_path)}")
        
        # Informações básicas
        info = self.get_image_info(file_path)
        if "error" not in info:
            parts.append(
                f"📐 Dimensões: {info['width']}x{info['height']} ({info['megapixels']} MP)"
            )
            parts.append(f"💾 Tamanho: {info['size_kb']} KB | Formato: {info['format']}")
            
            # Tipo de screenshot
            screenshot_type = self.detect_screenshot_type(file_path)
            parts.append(f"🎮 Tipo: {screenshot_type}")
        
        # OCR
        if include_ocr and TESSERACT_AVAILABLE:
            text = self.extract_text(file_path)
            if text and not text.startswith("["):
                # Limita tamanho do texto
                text_preview = text[:200] + "..." if len(text) > 200 else text
                parts.append(f"📝 Texto detectado:\n{text_preview}")
        
        # Cores dominantes
        if include_colors and CV_AVAILABLE:
            colors = self.get_dominant_colors(file_path, top_k=3)
            if colors[0][0] != "OpenCV não disponível":
                color_str = ", ".join([c[0] for c in colors])
                parts.append(f"🎨 Cores dominantes: {color_str}")
        
        if len(parts) == 1:
            parts.append("✅ Análise básica concluída")
        
        return "\n".join(parts)

    def quick_summary(self, file_path: str) -> str:
        """
        Retorna um resumo rápido de uma linha sobre a imagem.
        
        Returns:
            String resumida
        """
        info = self.get_image_info(file_path)
        if "error" in info:
            return f"❌ Erro: {info['error']}"
        
        return f"📸 {info['width']}x{info['height']} | {info['size_kb']} KB | {info['format']}"