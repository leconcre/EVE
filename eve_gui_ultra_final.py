# eve_gui_ultra_final.py - EVE v3.0 COM GROQ INTEGRADO
"""
EVE - Stellar Blade AI Assistant
Interface com integração Groq para código

FUNCIONALIDADES:
✅ Modo código com Groq Llama 70B
✅ Artefatos estilo Claude
✅ Modal de código 1000x750px
✅ Fallback para Ollama local
✅ Detecção automática de pedidos de código
"""

import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageDraw
import os
import json
import threading
import time
from datetime import datetime

# Importações do projeto
from code_artifacts import extract_and_save_artifacts, get_code_icon, clean_response_from_code

# Tenta importar Groq
try:
    from engines.groq_engine import GroqEngine
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq engine não encontrado")

# Tenta importar EVE local
try:
    from core.eve import Eve
    EVE_AVAILABLE = True
except ImportError:
    EVE_AVAILABLE = False
    print("⚠️ EVE core não encontrado")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════

GROQ_API_KEY = "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"

# ═══════════════════════════════════════════════════════════════════
# COMPONENTES AUXILIARES
# ═══════════════════════════════════════════════════════════════════

class SplashScreen(ctk.CTkToplevel):
    """Splash screen animada"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("")
        self.geometry("500x350")
        self.resizable(False, False)
        self.overrideredirect(True)
        
        x = (self.winfo_screenwidth() // 2) - 250
        y = (self.winfo_screenheight() // 2) - 175
        self.geometry(f"500x350+{x}+{y}")
        
        container = ctk.CTkFrame(self, fg_color="#000000", corner_radius=15, border_width=2, border_color="#00d9a3")
        container.pack(fill="both", expand=True, padx=3, pady=3)
        
        ctk.CTkLabel(container, text="⚡", font=ctk.CTkFont(size=70), text_color="#00d9a3").pack(pady=(60, 15))
        ctk.CTkLabel(container, text="EVE", font=ctk.CTkFont(size=40, weight="bold"), text_color="#00d9a3").pack()
        ctk.CTkLabel(container, text="Stellar Blade AI v3.0", font=ctk.CTkFont(size=14), text_color="#666666").pack(pady=5)
        
        self.progress = ctk.CTkProgressBar(container, width=350, height=6, corner_radius=3, fg_color="#1a1a1a", progress_color="#00d9a3")
        self.progress.pack(pady=30)
        self.progress.set(0)
        
        self.status = ctk.CTkLabel(container, text="Inicializando...", font=ctk.CTkFont(size=11), text_color="#666666")
        self.status.pack()
        self.after(100, self.animate)
    
    def animate(self):
        steps = [
            (0.2, "Carregando módulos..."),
            (0.4, "Conectando Groq..."),
            (0.6, "Inicializando EVE..."),
            (0.8, "Preparando interface..."),
            (1.0, "Pronto! ⚡")
        ]
        for val, txt in steps:
            self.progress.set(val)
            self.status.configure(text=txt)
            self.update()
            time.sleep(0.2)
        time.sleep(0.3)
        self.destroy()


class CustomDialog(ctk.CTkToplevel):
    """Dialog customizado"""
    def __init__(self, parent, title, message, type="info"):
        super().__init__(parent)
        self.result = None
        self.title("")
        
        height = min(max(250, 250 + len(message) // 50 * 20), 650)
        self.geometry(f"450x{height}")
        self.resizable(False, False)
        self.overrideredirect(True)
        
        x = (self.winfo_screenwidth() // 2) - 225
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"450x{height}+{x}+{y}")
        
        container = ctk.CTkFrame(self, fg_color="#000000", corner_radius=12, border_width=2, border_color="#00d9a3")
        container.pack(fill="both", expand=True, padx=2, pady=2)
        
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "question": "❓", "success": "✅"}
        ctk.CTkLabel(container, text=icons.get(type, "ℹ️"), font=ctk.CTkFont(size=50)).pack(pady=(30, 10))
        ctk.CTkLabel(container, text=title, font=ctk.CTkFont(size=18, weight="bold"), text_color="#ffffff").pack(pady=(0, 10))
        
        ctk.CTkLabel(container, text=message, font=ctk.CTkFont(size=13), text_color="#cccccc", wraplength=380).pack(pady=(0, 20))
        
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))
        
        if type == "question":
            ctk.CTkButton(btn_frame, text="SIM", command=lambda: self.close(True), width=100, height=35, corner_radius=8, fg_color="#00d9a3", hover_color="#00b589", text_color="#000000").pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="NÃO", command=lambda: self.close(False), width=100, height=35, corner_radius=8, fg_color="#333333", hover_color="#444444", text_color="#ffffff").pack(side="left", padx=5)
        else:
            ctk.CTkButton(btn_frame, text="OK", command=lambda: self.close(True), width=120, height=35, corner_radius=8, fg_color="#00d9a3", hover_color="#00b589", text_color="#000000").pack()
        
        self.grab_set()
        self.focus()
    
    def close(self, result):
        self.result = result
        self.destroy()


def show_info(parent, title, message):
    dialog = CustomDialog(parent, title, message, "info")
    parent.wait_window(dialog)

def show_error(parent, title, message):
    dialog = CustomDialog(parent, title, message, "error")
    parent.wait_window(dialog)

def show_warning(parent, title, message):
    dialog = CustomDialog(parent, title, message, "warning")
    parent.wait_window(dialog)

def ask_yes_no(parent, title, message):
    dialog = CustomDialog(parent, title, message, "question")
    parent.wait_window(dialog)
    return dialog.result


class CodeModal(ctk.CTkToplevel):
    """Modal estilo Claude para código - 1000x750px"""
    def __init__(self, parent, artifact, colors):
        super().__init__(parent)
        self.colors = colors

        # CORREÇÃO CRÍTICA: Valida que artifact é um dict válido
        if not isinstance(artifact, dict):
            print(f"[DEBUG] ❌ ERRO CodeModal: artifact não é dict! Tipo: {type(artifact)}")
            self.destroy()
            return

        if 'filename' not in artifact or 'language' not in artifact:
            print(f"[DEBUG] ❌ ERRO CodeModal: artifact faltando chaves! Keys: {artifact.keys()}")
            self.destroy()
            return

        self.artifact = artifact

        # Usa .get() com defaults para segurança
        filename = artifact.get('filename', 'code.txt')
        language = artifact.get('language', 'text')
        lines = artifact.get('lines', 0)
        size = artifact.get('size', 0)

        self.title(f"📄 {filename}")
        self.geometry("1000x750")
        self.transient(parent)
        self.grab_set()

        # Centraliza
        x = (self.winfo_screenwidth() // 2) - 500
        y = (self.winfo_screenheight() // 2) - 375
        self.geometry(f"1000x750+{x}+{y}")

        self.configure(fg_color=colors["bg"])

        # Header
        header = ctk.CTkFrame(self, fg_color=colors["bg_light"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        info_frame = ctk.CTkFrame(header, fg_color="transparent")
        info_frame.pack(side="left", padx=25, pady=20)

        icon = get_code_icon(language)
        ctk.CTkLabel(info_frame, text=icon, font=ctk.CTkFont(size=36)).pack(side="left", padx=(0, 15))

        text_info = ctk.CTkFrame(info_frame, fg_color="transparent")
        text_info.pack(side="left")
        ctk.CTkLabel(text_info, text=filename, font=ctk.CTkFont(size=18, weight="bold"), text_color=colors["secondary"]).pack(anchor="w")
        ctk.CTkLabel(text_info, text=f"{language.upper()} • {lines} linhas • {size} bytes", font=ctk.CTkFont(size=12), text_color=colors["text_dim"]).pack(anchor="w")
        
        # Botões
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=25, pady=20)
        
        ctk.CTkButton(btn_frame, text="📋 COPIAR", width=140, height=42, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"), fg_color=colors["accent"], hover_color=colors["accent_dim"], text_color="#000000", command=self.copy_code).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="✕", width=42, height=42, corner_radius=8, font=ctk.CTkFont(size=16, weight="bold"), fg_color=colors["bg_medium"], hover_color=colors["danger"], text_color=colors["text"], command=self.destroy).pack(side="left", padx=5)
        
        # Área de código
        code_frame = ctk.CTkFrame(self, fg_color="#0a0a0a", corner_radius=0)
        code_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Obtém código do artefato
        code_content = artifact.get('code', '')
        if not code_content and 'path' in artifact:
            try:
                with open(artifact['path'], 'r', encoding='utf-8') as f:
                    code_content = f.read()
            except:
                code_content = "# Erro ao carregar código"
        
        self.code_text = ctk.CTkTextbox(
            code_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0a0a0a",
            text_color="#e0e0e0",
            wrap="none",
            border_width=0,
            corner_radius=0
        )
        self.code_text.pack(fill="both", expand=True, padx=15, pady=15)
        self.code_text.insert("1.0", code_content)
        
        # Syntax highlighting básico
        self._apply_basic_highlighting()
    
    def _apply_basic_highlighting(self):
        """Aplica highlighting básico"""
        # Keywords Python em roxo
        keywords = ['def ', 'class ', 'import ', 'from ', 'return ', 'if ', 'else:', 'elif ', 'for ', 'while ', 'try:', 'except:', 'with ', 'as ', 'in ', 'not ', 'and ', 'or ', 'True', 'False', 'None', 'self', 'lambda ']
        
        self.code_text.tag_config("keyword", foreground="#c792ea")
        self.code_text.tag_config("string", foreground="#c3e88d")
        self.code_text.tag_config("comment", foreground="#546e7a")
        self.code_text.tag_config("function", foreground="#82aaff")
        
        content = self.code_text.get("1.0", "end")
        
        # Marca keywords
        for kw in keywords:
            start = "1.0"
            while True:
                pos = self.code_text.search(kw, start, stopindex="end")
                if not pos:
                    break
                end = f"{pos}+{len(kw)}c"
                self.code_text.tag_add("keyword", pos, end)
                start = end
    
    def copy_code(self):
        """Copia código para clipboard"""
        code = self.artifact.get('code', '')
        if not code and 'path' in self.artifact:
            try:
                with open(self.artifact['path'], 'r', encoding='utf-8') as f:
                    code = f.read()
            except:
                pass
        
        if code:
            self.clipboard_clear()
            self.clipboard_append(code)
            show_info(self, "✅ Copiado!", "Código copiado para a área de transferência!")
        else:
            show_error(self, "❌ Erro", "Não foi possível copiar o código")


# ═══════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class EVEApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Splash
        splash = SplashScreen(self)
        splash.grab_set()
        self.wait_window(splash)
        
        self.title("⚡ EVE - Stellar Blade AI v3.0")
        self.geometry("1600x950")
        self.minsize(1400, 800)
        
        # Cores
        self.colors = {
            "bg": "#000000",
            "bg_light": "#0a0a0a",
            "bg_medium": "#151515",
            "accent": "#00d9a3",
            "accent_dim": "#00b589",
            "accent_dark": "#008866",
            "secondary": "#00c4ff",
            "danger": "#ff2b5f",
            "text": "#ffffff",
            "text_dim": "#999999",
            "bubble_eve": "#0d0d0d",
            "bubble_user": "#1a1a1a",
            "groq_color": "#f97316"  # Laranja para Groq
        }
        self.configure(fg_color=self.colors["bg"])
        
        # Estado
        self.code_mode = False
        self.processing = False
        self.attached_files = []
        self.chat_history = []
        self.current_chat_id = None
        
        # Inicializa engines
        self._init_engines()
        
        # Carrega chats salvos
        self.saved_chats = self.load_chats()
        
        # Avatar
        self.load_avatar()
        
        # UI
        self.setup_ui()
        
        # Novo chat
        self.create_new_chat()

        # Handler de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handler para quando a janela é fechada."""
        print("🚀 Encerrando EVE...")
        if self.eve:
            self.eve.shutdown()
        self.destroy()
    
    def _init_engines(self):
        """Inicializa engines de IA"""
        # Groq
        self.groq = None
        self.groq_available = False
        
        if GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                self.groq = GroqEngine(GROQ_API_KEY)
                if self.groq.test_connection() == "OK":
                    self.groq_available = True
                    print("✅ Groq conectado!")
                else:
                    print("⚠️ Groq não respondeu")
            except Exception as e:
                print(f"❌ Erro Groq: {e}")
        
        # EVE local
        self.eve = None
        if EVE_AVAILABLE:
            try:
                self.eve = Eve(
                    personality_file="core/personality.txt",
                    memory_file="eve_memory.json",
                    enable_web_search=True
                )
                print("✅ EVE local inicializado!")
            except Exception as e:
                print(f"⚠️ EVE local falhou: {e}")
    
    def load_avatar(self):
        """Carrega avatar da EVE"""
        avatar_paths = [
            "eve_avatar.webp", "eve_avatar.png",
            "assets/eve_avatar.webp", "assets/eve_avatar.png"
        ]
        
        for path in avatar_paths:
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    img.thumbnail((60, 60), Image.Resampling.LANCZOS)
                    
                    # Máscara circular
                    mask = Image.new('L', (60, 60), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, 60, 60), fill=255)
                    
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    output = Image.new('RGBA', (60, 60), (0, 0, 0, 0))
                    output.paste(img.resize((60, 60)), (0, 0))
                    output.putalpha(mask)
                    
                    self.eve_avatar = ctk.CTkImage(output, output, size=(50, 50))
                    self.eve_avatar_large = ctk.CTkImage(output, output, size=(70, 70))
                    return
                except Exception as e:
                    print(f"Erro avatar: {e}")
        
        self.eve_avatar = None
        self.eve_avatar_large = None
    
    def setup_ui(self):
        """Configura interface"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # ═══════════════════════════════════════════════════════════
        # SIDEBAR
        # ═══════════════════════════════════════════════════════════
        sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=self.colors["bg_light"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)
        sidebar.grid_propagate(False)
        
        # Logo
        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=30, sticky="ew")
        
        if self.eve_avatar_large:
            ctk.CTkLabel(header, image=self.eve_avatar_large, text="").pack()
        else:
            ctk.CTkLabel(header, text="⚡", font=ctk.CTkFont(size=50), text_color=self.colors["accent"]).pack()
        
        ctk.CTkLabel(header, text="EVE", font=ctk.CTkFont(size=28, weight="bold"), text_color=self.colors["accent"]).pack(pady=(10,0))
        ctk.CTkLabel(header, text="STELLAR BLADE AI v3.0", font=ctk.CTkFont(size=11), text_color=self.colors["text_dim"]).pack()
        
        # Status Groq
        groq_status = "✅ GROQ ONLINE" if self.groq_available else "⚠️ GROQ OFFLINE"
        groq_color = self.colors["accent"] if self.groq_available else self.colors["danger"]
        ctk.CTkLabel(header, text=groq_status, font=ctk.CTkFont(size=10), text_color=groq_color).pack(pady=(5,0))
        
        # Botões
        ctk.CTkButton(
            sidebar, text="⚡ NOVO CHAT", command=self.create_new_chat,
            height=50, corner_radius=10, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors["accent"], hover_color=self.colors["accent_dim"], text_color="#000000"
        ).grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkButton(
            sidebar, text="🗑️ DELETAR", command=self.delete_chat,
            height=40, corner_radius=8, font=ctk.CTkFont(size=12),
            fg_color=self.colors["danger"], hover_color="#dd1f4f", text_color="#ffffff"
        ).grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        # Separador
        ctk.CTkFrame(sidebar, height=1, fg_color=self.colors["accent"]).grid(row=3, column=0, padx=40, pady=20, sticky="ew")
        
        # Label histórico
        ctk.CTkLabel(sidebar, text="📚 CONVERSAS", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_dim"], anchor="w").grid(row=4, column=0, padx=25, pady=(0,10), sticky="w")
        
        # Lista de chats
        self.history_frame = ctk.CTkScrollableFrame(
            sidebar, corner_radius=10, fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["accent"],
            scrollbar_button_hover_color=self.colors["accent_dim"]
        )
        self.history_frame.grid(row=5, column=0, padx=15, pady=(0,15), sticky="nsew")
        
        self.update_history_ui()
        
        # ═══════════════════════════════════════════════════════════
        # ÁREA PRINCIPAL
        # ═══════════════════════════════════════════════════════════
        main = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)
        
        # Header principal
        header_main = ctk.CTkFrame(main, height=90, corner_radius=0, fg_color=self.colors["bg_light"])
        header_main.grid(row=0, column=0, sticky="ew")
        header_main.grid_columnconfigure(0, weight=1)
        header_main.grid_propagate(False)
        
        header_left = ctk.CTkFrame(header_main, fg_color="transparent")
        header_left.grid(row=0, column=0, padx=30, pady=20, sticky="w")
        
        title_row = ctk.CTkFrame(header_left, fg_color="transparent")
        title_row.pack(anchor="w")
        
        ctk.CTkLabel(title_row, text="⚡", font=ctk.CTkFont(size=32), text_color=self.colors["accent"]).pack(side="left", padx=(0,10))
        
        title_text = ctk.CTkFrame(title_row, fg_color="transparent")
        title_text.pack(side="left")
        
        ctk.CTkLabel(title_text, text="CHAT COM EVE", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.colors["text"]).pack(anchor="w")
        self.subtitle = ctk.CTkLabel(title_text, text="Sistema neural online", font=ctk.CTkFont(size=12), text_color=self.colors["text_dim"])
        self.subtitle.pack(anchor="w")
        
        # Status badge
        status_frame = ctk.CTkFrame(header_main, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=30, pady=20, sticky="e")
        
        self.status_badge = ctk.CTkFrame(status_frame, corner_radius=15, fg_color=self.colors["bg_medium"], border_width=1, border_color=self.colors["accent"])
        self.status_badge.pack()
        
        self.status_dot = ctk.CTkLabel(self.status_badge, text="●", font=ctk.CTkFont(size=16), text_color=self.colors["accent"])
        self.status_dot.pack(side="left", padx=(12,5), pady=6)
        
        self.status_text = ctk.CTkLabel(self.status_badge, text="ONLINE", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text"])
        self.status_text.pack(side="left", padx=(0,12), pady=6)
        
        # ═══════════════════════════════════════════════════════════
        # ÁREA DE CHAT
        # ═══════════════════════════════════════════════════════════
        self.chat_frame = ctk.CTkScrollableFrame(
            main, corner_radius=0, fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["accent"],
            scrollbar_button_hover_color=self.colors["accent_dim"]
        )
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # ═══════════════════════════════════════════════════════════
        # ÁREA DE INPUT
        # ═══════════════════════════════════════════════════════════
        input_area = ctk.CTkFrame(main, corner_radius=0, fg_color=self.colors["bg_light"])
        input_area.grid(row=2, column=0, sticky="ew")
        input_area.grid_columnconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ctk.CTkFrame(input_area, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=3, padx=25, pady=(15,10), sticky="w")
        
        ctk.CTkLabel(toolbar, text="⚙️", font=ctk.CTkFont(size=16), text_color=self.colors["accent"]).pack(side="left", padx=(0,10))
        
        # Botão CÓDIGO (toggle)
        self.code_btn = ctk.CTkButton(
            toolbar, text="</> CÓDIGO", command=self.toggle_code_mode,
            width=120, height=32, corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.colors["bg_medium"],
            hover_color=self.colors["groq_color"],
            text_color=self.colors["text"],
            border_width=1, border_color=self.colors["text_dim"]
        )
        self.code_btn.pack(side="left", padx=3)
        
        # Outros botões
        ctk.CTkButton(
            toolbar, text="📊 RESUMIR", command=self.summarize,
            width=110, height=32, corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.colors["bg_medium"],
            hover_color=self.colors["secondary"],
            text_color=self.colors["text"],
            border_width=1, border_color=self.colors["text_dim"]
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            toolbar, text="💾 EXPORTAR", command=self.export_chat,
            width=110, height=32, corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.colors["bg_medium"],
            hover_color=self.colors["accent"],
            text_color=self.colors["text"],
            border_width=1, border_color=self.colors["text_dim"]
        ).pack(side="left", padx=3)
        
        # Preview de anexos
        self.attachments_display = ctk.CTkFrame(input_area, fg_color="transparent", height=0)
        self.attachments_display.grid(row=1, column=0, columnspan=3, padx=25, sticky="ew")
        self.attachments_display.grid_remove()
        
        # Linha de input
        input_row = ctk.CTkFrame(input_area, fg_color="transparent")
        input_row.grid(row=2, column=0, columnspan=3, padx=25, pady=(0,20), sticky="ew")
        input_row.grid_columnconfigure(1, weight=1)
        
        # Botão anexar
        ctk.CTkButton(
            input_row, text="📎", command=self.attach_file,
            width=55, height=65, corner_radius=10,
            font=ctk.CTkFont(size=20),
            fg_color=self.colors["bg_medium"],
            hover_color=self.colors["accent"],
            text_color=self.colors["text"]
        ).grid(row=0, column=0, padx=(0,10))
        
        # Campo de texto
        input_frame = ctk.CTkFrame(
            input_row, fg_color=self.colors["bg_medium"],
            corner_radius=10, border_width=2, border_color=self.colors["accent"]
        )
        input_frame.grid(row=0, column=1, sticky="ew", padx=(0,10))
        
        self.input_box = ctk.CTkTextbox(
            input_frame, height=65, corner_radius=10,
            font=ctk.CTkFont(size=13), wrap="word",
            fg_color=self.colors["bg_medium"],
            text_color=self.colors["text"], border_width=0
        )
        self.input_box.pack(fill="both", expand=True, padx=15, pady=10)
        self.input_box.bind("<Return>", self.send_enter)
        
        # Botão enviar
        self.send_btn = ctk.CTkButton(
            input_row, text="➤", command=self.send_message,
            width=55, height=65, corner_radius=10,
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_dim"],
            text_color="#000000"
        )
        self.send_btn.grid(row=0, column=2)
    
    # ═══════════════════════════════════════════════════════════════════
    # MÉTODOS DE ESTADO
    # ═══════════════════════════════════════════════════════════════════
    
    def set_status(self, online=True, text=None):
        """Atualiza badge de status"""
        if online:
            self.status_dot.configure(text_color=self.colors["accent"])
            self.status_text.configure(text=text or "ONLINE")
            self.status_badge.configure(border_color=self.colors["accent"])
        else:
            self.status_dot.configure(text_color=self.colors["secondary"])
            self.status_text.configure(text=text or "PROCESSANDO")
            self.status_badge.configure(border_color=self.colors["secondary"])
    
    def toggle_code_mode(self):
        """Alterna modo código (usa Groq)"""
        self.code_mode = not self.code_mode
        
        if self.code_mode:
            self.code_btn.configure(
                fg_color=self.colors["groq_color"],
                text_color="#ffffff",
                border_color=self.colors["groq_color"],
                text="</> GROQ 70B"
            )
            self.subtitle.configure(text="⚡ MODO CÓDIGO - Groq Llama 70B")
            self.set_status(True, "GROQ")
        else:
            self.code_btn.configure(
                fg_color=self.colors["bg_medium"],
                text_color=self.colors["text"],
                border_color=self.colors["text_dim"],
                text="</> CÓDIGO"
            )
            self.subtitle.configure(text="Sistema neural online")
            self.set_status(True, "ONLINE")
    
    def _detect_code_request(self, msg: str) -> bool:
        """Detecta se mensagem pede código"""
        msg_lower = msg.lower()
        
        triggers = [
            "código", "codigo", "code",
            "programa", "script", "função", "funcao",
            "crie um", "cria um", "faça um", "faca um",
            "implementa", "implemente", "desenvolva",
            "[modo código]", "[modo codigo]",
            "gere código", "gere codigo",
            "escreva um programa", "escreva código"
        ]
        
        return any(trigger in msg_lower for trigger in triggers)
    
    # ═══════════════════════════════════════════════════════════════════
    # BUBBLES DE CHAT
    # ═══════════════════════════════════════════════════════════════════
    
    def create_bubble(self, text, is_user):
        """Cria bubble de mensagem"""
        container = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        container.pack(fill="x", padx=30, pady=10)
        
        if is_user:
            # Bubble do usuário (direita)
            bubble = ctk.CTkFrame(
                container, fg_color=self.colors["bubble_user"],
                corner_radius=15, border_width=1, border_color=self.colors["bg_medium"]
            )
            bubble.pack(side="right", padx=10)
            
            ctk.CTkLabel(
                bubble, text=text, font=ctk.CTkFont(size=13),
                wraplength=700, justify="left", text_color=self.colors["text"]
            ).pack(padx=20, pady=14)
            
            ctk.CTkLabel(
                container, text="👤", font=ctk.CTkFont(size=28),
                text_color=self.colors["secondary"]
            ).pack(side="right", padx=5)
        else:
            # Bubble da EVE (esquerda)
            if self.eve_avatar:
                ctk.CTkLabel(container, image=self.eve_avatar, text="").pack(side="left", padx=5)
            else:
                ctk.CTkLabel(container, text="⚡", font=ctk.CTkFont(size=28), text_color=self.colors["accent"]).pack(side="left", padx=5)
            
            bubble = ctk.CTkFrame(
                container, fg_color=self.colors["bubble_eve"],
                corner_radius=15, border_width=1, border_color=self.colors["accent"]
            )
            bubble.pack(side="left", padx=10)
            
            # Header
            name_row = ctk.CTkFrame(bubble, fg_color="transparent")
            name_row.pack(anchor="w", padx=20, pady=(12,0))
            
            ctk.CTkLabel(name_row, text="EVE", font=ctk.CTkFont(size=10, weight="bold"), text_color=self.colors["accent"]).pack(side="left")
            
            if self.code_mode:
                ctk.CTkLabel(name_row, text=" • GROQ 70B", font=ctk.CTkFont(size=9), text_color=self.colors["groq_color"]).pack(side="left")
            else:
                ctk.CTkLabel(name_row, text=" • ONLINE", font=ctk.CTkFont(size=9), text_color=self.colors["accent"]).pack(side="left")
            
            # Texto
            ctk.CTkLabel(
                bubble, text=text, font=ctk.CTkFont(size=13),
                wraplength=700, justify="left", text_color=self.colors["text"]
            ).pack(padx=20, pady=(6,14))
        
        # Scroll para baixo
        self.update_idletasks()
        self.chat_frame._parent_canvas.yview_moveto(1.0)
    
    def create_code_artifact_bubble(self, text, artifacts):
        """Cria bubble com botão de artefato de código"""
        # CORREÇÃO: Valida que artifacts é uma lista
        if not isinstance(artifacts, list):
            print(f"[DEBUG] ❌ ERRO: artifacts não é lista! Tipo: {type(artifacts)}")
            # Fallback: mostra como texto normal
            self.create_bubble(text if text else "Código gerado", False)
            return

        container = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        container.pack(fill="x", padx=30, pady=10)

        # Avatar
        if self.eve_avatar:
            ctk.CTkLabel(container, image=self.eve_avatar, text="").pack(side="left", padx=5, anchor="n")
        else:
            ctk.CTkLabel(container, text="⚡", font=ctk.CTkFont(size=28), text_color=self.colors["accent"]).pack(side="left", padx=5, anchor="n")

        # Container do conteúdo
        content_container = ctk.CTkFrame(container, fg_color="transparent")
        content_container.pack(side="left", fill="x", expand=True, padx=10)

        # Bubble principal
        bubble = ctk.CTkFrame(
            content_container, fg_color=self.colors["bubble_eve"],
            corner_radius=15, border_width=1, border_color=self.colors["accent"]
        )
        bubble.pack(fill="x")

        # Header
        name_row = ctk.CTkFrame(bubble, fg_color="transparent")
        name_row.pack(anchor="w", padx=20, pady=(12,0))

        ctk.CTkLabel(name_row, text="EVE", font=ctk.CTkFont(size=10, weight="bold"), text_color=self.colors["accent"]).pack(side="left")
        ctk.CTkLabel(name_row, text=" • GROQ 70B", font=ctk.CTkFont(size=9), text_color=self.colors["groq_color"]).pack(side="left")
        ctk.CTkLabel(name_row, text=" • CÓDIGO", font=ctk.CTkFont(size=9), text_color=self.colors["secondary"]).pack(side="left")

        # Texto explicativo
        if text and text.strip():
            ctk.CTkLabel(
                bubble, text=text, font=ctk.CTkFont(size=13),
                wraplength=700, justify="left", text_color=self.colors["text"]
            ).pack(padx=20, pady=(6,10))

        # Botões de artefatos
        for i, artifact in enumerate(artifacts):
            # CORREÇÃO: Valida cada artefato antes de usar
            if not isinstance(artifact, dict):
                print(f"[DEBUG] ⚠️ Artefato {i} não é dict, pulando. Tipo: {type(artifact)}")
                continue

            if 'language' not in artifact or 'filename' not in artifact:
                print(f"[DEBUG] ⚠️ Artefato {i} faltando chaves necessárias: {artifact.keys()}")
                continue

            btn_container = ctk.CTkFrame(bubble, fg_color="transparent")
            btn_container.pack(fill="x", padx=15, pady=(0,10))

            try:
                icon = get_code_icon(artifact.get('language', 'text'))
                filename = artifact.get('filename', 'code.txt')
                language = artifact.get('language', 'text')
                lines = artifact.get('lines', 0)

                # Botão clicável
                artifact_btn = ctk.CTkButton(
                    btn_container,
                    text=f"{icon} {filename}",
                    width=500, height=50, corner_radius=8,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color="#1a1a1a",
                    hover_color=self.colors["secondary"],
                    text_color=self.colors["text"],
                    anchor="w",
                    border_width=2,
                    border_color=self.colors["secondary"],
                    command=lambda a=artifact: self.open_code_modal(a)
                )
                artifact_btn.pack(side="left", fill="x", expand=True, padx=(0,10))

                # Info
                ctk.CTkLabel(
                    btn_container,
                    text=f"{language.upper()} • {lines} linhas",
                    font=ctk.CTkFont(size=10),
                    text_color=self.colors["text_dim"]
                ).pack(side="right")
            except Exception as e:
                print(f"[DEBUG] ⚠️ Erro ao criar botão para artefato {i}: {e}")
                import traceback
                traceback.print_exc()

        ctk.CTkLabel(bubble, text="", height=5).pack()

        # Scroll para baixo
        self.update_idletasks()
        self.chat_frame._parent_canvas.yview_moveto(1.0)
    
    def open_code_modal(self, artifact):
        """Abre modal de código"""
        print(f"[DEBUG] open_code_modal chamado")
        print(f"[DEBUG] Tipo do artifact: {type(artifact)}")
        print(f"[DEBUG] Conteúdo do artifact: {artifact if isinstance(artifact, dict) else str(artifact)[:200]}")

        # VALIDAÇÃO EXTRA antes de abrir modal
        if not isinstance(artifact, dict):
            print(f"[DEBUG] ❌ ERRO: Artifact não é dict no open_code_modal!")
            self.create_bubble(f"❌ Erro ao abrir código: dados inválidos (tipo: {type(artifact)})", False)
            return

        if 'code' not in artifact:
            print(f"[DEBUG] ❌ ERRO: Artifact sem campo 'code'!")
            self.create_bubble("❌ Erro ao abrir código: código não encontrado", False)
            return

        try:
            CodeModal(self, artifact, self.colors)
        except Exception as e:
            print(f"[DEBUG] ❌ ERRO ao criar CodeModal: {e}")
            import traceback
            traceback.print_exc()
            self.create_bubble(f"❌ Erro ao abrir código: {e}", False)
    
    # ═══════════════════════════════════════════════════════════════════
    # ENVIO DE MENSAGENS
    # ═══════════════════════════════════════════════════════════════════
    
    def send_enter(self, e):
        """Handler para Enter"""
        if not e.state & 0x1:  # Sem Shift
            self.send_message()
            return "break"
    
    def send_message(self):
        """Envia mensagem"""
        if self.processing:
            return
        
        msg = self.input_box.get("1.0", "end-1c").strip()
        if not msg and not self.attached_files:
            return
        
        # Limpa input
        self.input_box.delete("1.0", "end")
        
        # Estado de processamento
        self.processing = True
        self.input_box.configure(state="disabled")
        self.send_btn.configure(state="disabled", text="⏳", fg_color=self.colors["text_dim"])
        self.set_status(False, "PROCESSANDO")
        self.subtitle.configure(text="⚡ EVE processando...")
        
        # Bubble do usuário
        self.create_bubble(msg if msg else "[Imagem]", True)
        self.chat_history.append({
            "role": "user",
            "content": msg,
            "timestamp": datetime.now().isoformat()
        })
        
        # Copia anexos
        files_to_send = self.attached_files.copy()
        self.attached_files = []
        self.update_attachments_display()
        
        # Processa em thread
        threading.Thread(target=self.process_message, args=(msg, files_to_send), daemon=True).start()
    
    def _restore_ui(self):
        """Restaura UI após processar mensagem"""
        self.input_box.configure(state="normal")
        self.input_box.delete("1.0", "end")
        self.send_btn.configure(state="normal", text="➤", fg_color=self.colors["accent"])

        if self.code_mode:
            self.set_status(True, "GROQ")
            self.subtitle.configure(text="⚡ MODO CÓDIGO - Groq Llama 70B")
        else:
            self.set_status(True, "ONLINE")
            self.subtitle.configure(text="Sistema neural online")

        self.input_box.focus()
        self.processing = False

    def process_message(self, msg, files):
        """Processa mensagem (thread separada) - CORREÇÃO: Com timeout e fallback"""
        # PROTEÇÃO TOTAL: Captura QUALQUER erro e mostra resposta sem crashar
        try:
            self._process_message_internal(msg, files)
        except Exception as critical_error:
            print(f"[DEBUG] ❌❌❌ ERRO CRÍTICO: {critical_error}")
            import traceback
            traceback.print_exc()

            # Mostra erro para o usuário sem crashar
            self.after(0, lambda: self.create_bubble(
                f"❌ Erro ao processar: {str(critical_error)[:200]}",
                False
            ))
            self.after(0, self._restore_ui)

    def _process_message_internal(self, msg, files):
        """Processamento interno de mensagem"""
        import signal

        # CORREÇÃO: Timeout de 60 segundos para evitar travamentos
        def timeout_handler():
            print("[DEBUG] ⏰ TIMEOUT de 60s atingido!")
            self.after(0, lambda: self.create_bubble(
                "⏰ Timeout: A resposta demorou muito. Tente novamente com uma pergunta mais simples.",
                False
            ))
            self.after(0, self._restore_ui)

        try:
            print(f"\n[DEBUG] Mensagem: {msg[:50]}...")
            print(f"[DEBUG] Modo código: {self.code_mode}")
            print(f"[DEBUG] Arquivos: {len(files) if files else 0}")

            if not self.eve:
                self.after(0, lambda: self.create_bubble("❌ EVE local não disponível.", False))
                self.after(0, self._restore_ui)
                return

            # Determina a escolha do modelo
            model_choice = None
            auto_code_mode = self._detect_code_request(msg)
            use_groq = self.code_mode or auto_code_mode

            if use_groq and self.groq_available and not files:
                print("[DEBUG] 🚀 Usando GROQ para código...")
                self.after(0, lambda: self.set_status(False, "GROQ"))
                model_choice = "groq"
            elif files:
                print("[DEBUG] 🖼️ Processando imagem...")
                model_choice = "qwen3-vl:8b"
            else:
                print("[DEBUG] 💬 Modo chat normal...")

            # CORREÇÃO: Timer de timeout
            import threading
            timeout_timer = threading.Timer(60.0, timeout_handler)
            timeout_timer.daemon = True
            timeout_timer.start()

            # Gera a resposta através do motor principal da EVE
            print("[DEBUG] Chamando eve.generate_response()...")
            try:
                response = self.eve.generate_response(
                    msg,
                    model_choice=model_choice,
                    files=files,
                    max_tokens=2500 if use_groq else 1500,  # CORREÇÃO: Reduzido tokens
                )
                timeout_timer.cancel()  # Cancela timer se completou
                print(f"[DEBUG] Resposta recebida: {type(response)}")
            except Exception as gen_error:
                timeout_timer.cancel()
                print(f"[DEBUG] ❌ Erro ao gerar resposta: {gen_error}")
                import traceback
                traceback.print_exc()

                # CORREÇÃO: Mensagem de erro mais clara
                error_msg = f"❌ Erro: {str(gen_error)[:100]}"
                if "timeout" in str(gen_error).lower():
                    error_msg = "⏰ A requisição demorou muito. Tente uma pergunta mais simples."
                elif "groq" in str(gen_error).lower():
                    error_msg = "❌ Groq indisponível. Tente novamente ou desative o modo código."

                self.after(0, lambda: self.create_bubble(error_msg, False))
                self.after(0, self._restore_ui)
                return

            # Extrai texto, artefatos e metadados
            response_text = response.get("text", "")
            artifacts = response.get("artifacts")
            model_used = response.get("model_used", "unknown")
            web_search_used = response.get("web_search_used", False)

            print(f"[DEBUG] response_text: {len(response_text)} chars")
            print(f"[DEBUG] model_used: {model_used}")
            print(f"[DEBUG] web_search_used: {web_search_used}")

            # Determina indicador de modelo
            model_indicator = ""
            if "groq" in model_used:
                if web_search_used:
                    model_indicator = " ☁️🔍"  # Nuvem + busca
                else:
                    model_indicator = " ☁️"    # Só nuvem
            elif "ollama" in model_used:
                if web_search_used:
                    model_indicator = " 💻🔍"  # Local + busca
                else:
                    model_indicator = " 💻"    # Local

            # Adiciona indicador ao texto da resposta
            if model_indicator:
                response_text = f"{response_text}{model_indicator}"

            # ═══════════════════════════════════════════════════════
            # EXIBE RESPOSTA
            # ═══════════════════════════════════════════════════════
            # CORREÇÃO: Verifica se artifacts é True (boolean) ou lista
            has_artifacts = artifacts is True or (isinstance(artifacts, list) and len(artifacts) > 0)

            if has_artifacts:
                # PROTEÇÃO TOTAL: Se der QUALQUER erro com artefatos, mostra como texto normal
                try:
                    # Com artefatos de código
                    print("[DEBUG] 🎨 Processando artefatos de código...")
                    clean_text = clean_response_from_code(response_text)

                    # Salva os artefatos de código
                    saved_artifacts = extract_and_save_artifacts(response_text)
                    print(f"[DEBUG] Tipo de saved_artifacts: {type(saved_artifacts)}")
                    print(f"[DEBUG] Artefatos extraídos: {len(saved_artifacts) if saved_artifacts else 0}")

                    # Valida que saved_artifacts é uma lista de dicts
                    if not (saved_artifacts and isinstance(saved_artifacts, list) and len(saved_artifacts) > 0):
                        raise ValueError("Nenhum artefato válido extraído")

                    # Verifica se todos os itens são dicts válidos
                    valid_artifacts = []
                    for i, art in enumerate(saved_artifacts):
                        if isinstance(art, dict) and 'filename' in art and 'language' in art and 'code' in art:
                            valid_artifacts.append(art)
                        else:
                            print(f"[DEBUG] ⚠️ Artefato {i} inválido: tipo={type(art)}, conteúdo={art}")

                    if not valid_artifacts:
                        raise ValueError("Nenhum artefato válido após validação")

                    # Exibe artefatos
                    def show_artifacts():
                        print("[DEBUG] Exibindo artefatos na GUI...")
                        try:
                            self.create_code_artifact_bubble(clean_text, valid_artifacts)
                            self.chat_history.append({
                                "role": "assistant",
                                "content": response_text,
                                "artifacts": [a.get('filename', 'code') for a in valid_artifacts],
                                "timestamp": datetime.now().isoformat()
                            })
                            self.save_chat()
                            print("[DEBUG] ✅ Artefatos exibidos com sucesso")
                        except Exception as e:
                            print(f"[DEBUG] ❌ Erro ao exibir artefatos: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            self._restore_ui()

                    self.after(0, show_artifacts)

                except Exception as artifact_error:
                    print(f"[DEBUG] ❌ ERRO ao processar artefatos: {artifact_error}")
                    import traceback
                    traceback.print_exc()

                    # FALLBACK: Mostra como texto normal se der QUALQUER erro
                    print("[DEBUG] ⚠️ Caindo no fallback - mostrando como texto normal")
                    self.chat_history.append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.now().isoformat()
                    })

                    def show_response_fallback():
                        try:
                            self.create_bubble(response_text, False)
                            self.save_chat()
                        finally:
                            self._restore_ui()

                    self.after(0, show_response_fallback)
            else:
                # Sem artefatos
                if not response_text:
                    print("[DEBUG] ⚠️ Resposta de texto vazia, não exibindo bolha.")
                    self.after(0, self._restore_ui)  # Restaura UI mesmo se vazio
                    return

                self.chat_history.append({
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().isoformat()
                })

                def show_response():
                    print("[DEBUG] Exibindo resposta de texto normal...")
                    try:
                        self.create_bubble(response_text, False)
                        self.save_chat()
                        self.update_idletasks()  # Força atualização da GUI
                        self.update()  # Força redesenho completo
                        print("[DEBUG] ✅ Resposta de texto exibida")
                    finally:
                        self._restore_ui()

                self.after(0, show_response)

            print("[DEBUG] ✅ Processo concluído")

        except Exception as e:
            print(f"[DEBUG] ❌ Erro: {e}")
            import traceback
            traceback.print_exc()

            def show_error():
                self.create_bubble(f"❌ Erro: {e}", False)
                self._restore_ui()

            self.after(0, show_error)
    
    # ═══════════════════════════════════════════════════════════════════
    # ANEXOS
    # ═══════════════════════════════════════════════════════════════════
    
    def attach_file(self):
        """Anexa arquivo"""
        f = filedialog.askopenfilename(
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")]
        )
        if f:
            self.attached_files.append(f)
            self.update_attachments_display()
    
    def update_attachments_display(self):
        """Atualiza preview de anexos"""
        for w in self.attachments_display.winfo_children():
            w.destroy()
        
        if not self.attached_files:
            self.attachments_display.grid_remove()
            return
        
        self.attachments_display.grid()
        self.attachments_display.configure(height=60)
        
        for f in self.attached_files:
            frame = ctk.CTkFrame(
                self.attachments_display, fg_color=self.colors["bg_medium"],
                corner_radius=8, border_width=1, border_color=self.colors["accent"]
            )
            frame.pack(side="left", padx=5, pady=5)
            
            ctk.CTkLabel(
                frame, text=f"📎 {os.path.basename(f)[:20]}",
                font=ctk.CTkFont(size=10)
            ).pack(side="left", padx=10, pady=5)
            
            ctk.CTkButton(
                frame, text="✕", width=20, height=20,
                fg_color="transparent", hover_color=self.colors["danger"],
                text_color=self.colors["text"],
                command=lambda file=f: self.remove_attachment(file)
            ).pack(side="right", padx=5)
    
    def remove_attachment(self, file):
        """Remove anexo"""
        self.attached_files.remove(file)
        self.update_attachments_display()
    
    # ═══════════════════════════════════════════════════════════════════
    # AÇÕES
    # ═══════════════════════════════════════════════════════════════════
    
    def summarize(self):
        """Mostra resumo do chat"""
        if not self.chat_history:
            show_warning(self, "Aviso", "Nenhuma conversa para resumir")
            return
        
        topics = [" ".join(m["content"].split()[:5]) for m in self.chat_history if m["role"] == "user"]
        
        summary = f"""📊 RESUMO DO CHAT

Total de mensagens: {len(self.chat_history)}
Suas mensagens: {sum(1 for m in self.chat_history if m['role']=='user')}
Respostas EVE: {sum(1 for m in self.chat_history if m['role']=='assistant')}

Tópicos abordados:
{chr(10).join(f'  • {t}' for t in topics[:5])}"""
        
        show_info(self, "📊 Resumo", summary)
    
    def export_chat(self):
        """Exporta chat"""
        if not self.chat_history:
            show_warning(self, "Aviso", "Nenhuma conversa para exportar")
            return
        
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("JSON", "*.json")]
        )
        
        if f:
            try:
                if f.endswith(".json"):
                    with open(f, "w", encoding="utf-8") as file:
                        json.dump(self.chat_history, file, ensure_ascii=False, indent=2)
                else:
                    with open(f, "w", encoding="utf-8") as file:
                        for m in self.chat_history:
                            role = "Você" if m['role'] == 'user' else "EVE"
                            file.write(f"{role}: {m['content']}\n\n")
                
                show_info(self, "✅ Sucesso", f"Chat exportado para:\n{f}")
            except Exception as e:
                show_error(self, "❌ Erro", str(e))
    
    def delete_chat(self):
        """Deleta chat atual"""
        if not self.chat_history:
            show_warning(self, "Aviso", "Nenhuma conversa para deletar")
            return
        
        if ask_yes_no(self, "⚠️ DELETAR CHAT", "Esta ação é irreversível!\n\nDeletar esta conversa?"):
            if self.current_chat_id in self.saved_chats:
                del self.saved_chats[self.current_chat_id]
                self.save_all_chats()
            
            for w in self.chat_frame.winfo_children():
                w.destroy()
            
            self.chat_history = []
            self.update_history_ui()
            self.create_bubble("💀 Chat deletado. Começando novo...", False)
    
    # ═══════════════════════════════════════════════════════════════════
    # GERENCIAMENTO DE CHATS
    # ═══════════════════════════════════════════════════════════════════
    
    def create_new_chat(self):
        """Cria novo chat"""
        if self.current_chat_id and self.chat_history:
            self.save_chat()
        
        self.chat_history = []
        self.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for w in self.chat_frame.winfo_children():
            w.destroy()
        
        # Mensagem inicial
        welcome = "Oi! ⚡ Sou a EVE, sua assistente virtual.\n\n"
        if self.groq_available:
            welcome += "🚀 Groq Llama 70B está online para código!\nClique em '</> CÓDIGO' para ativar.\n\n"
        welcome += "Como posso ajudar? 🎮💻"
        
        self.create_bubble(welcome, False)
    
    def save_chat(self):
        """Salva chat atual"""
        if not self.chat_history:
            return
        
        # Título = primeira mensagem do usuário
        title = "Novo Chat"
        for m in self.chat_history:
            if m["role"] == "user":
                title = m["content"][:45] + ("..." if len(m["content"]) > 45 else "")
                break
        
        self.saved_chats[self.current_chat_id] = {
            "title": title,
            "messages": self.chat_history,
            "timestamp": datetime.now().isoformat()
        }
        
        self.save_all_chats()
        self.update_history_ui()
    
    def save_all_chats(self):
        """Salva todos os chats no disco"""
        try:
            with open("eve_chats.json", "w", encoding="utf-8") as f:
                json.dump(self.saved_chats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar chats: {e}")
    
    def load_chats(self):
        """Carrega chats salvos"""
        try:
            if os.path.exists("eve_chats.json"):
                with open("eve_chats.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def update_history_ui(self):
        """Atualiza lista de chats na sidebar"""
        for w in self.history_frame.winfo_children():
            w.destroy()
        
        if not self.saved_chats:
            ctk.CTkLabel(
                self.history_frame, text="Nenhuma conversa",
                font=ctk.CTkFont(size=11), text_color=self.colors["text_dim"]
            ).pack(pady=30)
            return
        
        # Ordena por data
        chats = sorted(
            self.saved_chats.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True
        )
        
        for cid, data in chats[:20]:
            title = data.get("title", "Chat")
            display_title = title[:35] + ("..." if len(title) > 35 else "")
            
            ctk.CTkButton(
                self.history_frame, text=display_title,
                command=lambda c=cid: self.load_chat(c),
                anchor="w", height=40, corner_radius=8,
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                hover_color=self.colors["bg_medium"],
                text_color=self.colors["text"],
                border_width=1, border_color=self.colors["bg_medium"]
            ).pack(fill="x", padx=5, pady=3)
    
    def load_chat(self, cid):
        """Carrega chat específico"""
        if cid in self.saved_chats:
            if self.current_chat_id and self.chat_history:
                self.save_chat()
            
            self.current_chat_id = cid
            self.chat_history = self.saved_chats[cid]["messages"]
            
            for w in self.chat_frame.winfo_children():
                w.destroy()
            
            for m in self.chat_history:
                is_user = m["role"] == "user"
                
                # Verifica se a mensagem tem artefatos
                if not is_user and "artifacts" in m and m["artifacts"]:
                    raw_content = m.get("content", "")

                    # Se artifacts for True (booleano), extrai do texto
                    if m["artifacts"] is True:
                        print(f"[LOAD] Detectado artifacts=True, extraindo do texto...")
                        # Extrai artefatos do conteúdo
                        artifacts_data = extract_and_save_artifacts(raw_content)
                        clean_text = clean_response_from_code(raw_content)
                    elif isinstance(m["artifacts"], list):
                        # Formato antigo: lista de filenames
                        clean_text = clean_response_from_code(raw_content)
                        artifacts_data = []
                        for filename in m["artifacts"]:
                            artifact_path = os.path.join("code_artifacts", filename)
                            code_content = ""
                            lines = 0
                            size = 0
                            if os.path.exists(artifact_path):
                                try:
                                    with open(artifact_path, 'r', encoding='utf-8') as f:
                                        code_content = f.read()
                                    lines = code_content.count('\n') + 1
                                    size = os.path.getsize(artifact_path)
                                except Exception as e:
                                    print(f"Erro ao ler artefato salvo: {e}")

                            artifacts_data.append({"filename": filename, "language": "python", "lines": lines, "size": size, "code": code_content, "path": artifact_path})
                    else:
                        # Fallback: trata como texto normal
                        print(f"[LOAD] Formato de artifacts desconhecido: {type(m['artifacts'])}")
                        content = raw_content
                        self.create_bubble(str(content), is_user)
                        continue

                    if artifacts_data:
                        self.create_code_artifact_bubble(clean_text, artifacts_data)
                    else:
                        print(f"[LOAD] Nenhum artefato extraído, mostrando como texto")
                        self.create_bubble(raw_content, is_user)
                else:
                    content = m.get("content", "")
                    # Adicionado para lidar com o formato antigo de resposta
                    if isinstance(content, dict) and 'text' in content:
                        content = content['text']
                    self.create_bubble(str(content), is_user)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("EVE - Stellar Blade AI v3.0")
    print("="*60)
    print(f"Groq disponível: {GROQ_AVAILABLE}")
    print(f"EVE disponível: {EVE_AVAILABLE}")
    print("="*60 + "\n")
    
    app = EVEApp()
    app.mainloop()