# main.py
import os
import sys
import logging
import random
import re
from core.eve import Eve
import atexit

LOG_FILE = "logs/eve_session.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Remove handlers de console
for handler in logging.root.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
        logging.root.removeHandler(handler)

PERSONALITY_FILE = os.path.join("core", "personality.txt")

def print_flush(text):
    """Print com flush imediato"""
    print(text)
    sys.stdout.flush()

def clear_line():
    """Limpa linha atual"""
    sys.stdout.write('\r')
    sys.stdout.write(' ' * 80)
    sys.stdout.write('\r')
    sys.stdout.flush()

def detect_buggy_response(response: str) -> bool:
    """Apenas detecta vazamentos críticos"""
    # Só bloqueia se vazar texto literal da personalidade
    if "PERSONALIDADE CORE:" in response or "REGRAS CRÍTICAS:" in response:
        return True
    return False

def main():
    eve = Eve(personality_file=PERSONALITY_FILE)

    # Registra a função de desligamento para ser chamada na saída
    def shutdown_eve():
        print_flush("\nSalvando sessão e desligando EVE...")
        eve.shutdown()
    atexit.register(shutdown_eve)

    print_flush("\n╔═══════════════════════════════════════╗")
    print_flush("║       🖤 EVE Online - v2.0           ║")
    print_flush("║   Assistente Virtual Inteligente     ║")
    print_flush("╚═══════════════════════════════════════╝\n")
    print_flush("💡 Dica: Para sair, digite 'sair'")
    print_flush("📎 Para analisar imagens, cole o caminho\n")

    welcome_response = eve.generate_response(
        "cumprimento inicial breve",
        max_tokens=200,  # Limite para cumprimento
        temperature=0.8
    )
    welcome_msg = welcome_response.get("text", "Olá!")
    print_flush(f"EVE: {welcome_msg}\n")
    logging.info("=== Sessão iniciada ===")

    while True:
        try:
            sys.stdout.flush()
            sys.stderr.flush()

            user_input = input("Você: ").strip()
            sys.stdout.flush()

            # Comandos de saída
            if user_input.lower() in ["sair", "exit", "quit", "tchau", "bye"]:
                farewell_response = eve.generate_response(
                    "despedida breve",
                    max_tokens=150,
                    temperature=0.8
                )
                farewell_msg = farewell_response.get("text", "Até logo! 💜")
                print_flush(f"\nEVE: {farewell_msg}\n")
                # atexit cuidará do salvamento e log de encerramento
                break

            if not user_input:
                continue

            # --- Detecção de imagens ---
            attachments = []
            
            path_pattern = r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'
            potential_paths = re.findall(path_pattern, user_input)
            
            for path in potential_paths:
                if os.path.isfile(path) and path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")):
                    attachments.append(path)
                    user_input = user_input.replace(path, "").strip()
                    logging.info(f"Imagem: {path}")
            
            if not user_input and attachments:
                user_input = "Analise esta imagem brevemente"

            # Indica processamento com indicador de modo
            if attachments:
                print_flush("🖼️  Analisando imagem...")
            else:
                # Verifica se tem Groq disponível
                has_groq = hasattr(eve, 'groq_engine') and eve.groq_engine is not None
                if has_groq:
                    print_flush("💭 EVE está pensando... ☁️")  # Ícone de nuvem
                else:
                    print_flush("💭 EVE está pensando... 💻")  # Ícone local
            sys.stdout.flush()

            # Define max_tokens baseado no tipo de pergunta
            max_tokens = 1024  # Padrão generoso

            # Saudações simples = menos tokens
            simple_words = ["oi", "olá", "hi", "tudo bem", "como vai", "ok", "entendi"]
            if user_input.lower().strip() in simple_words:
                max_tokens = 300

            # Perguntas complexas, código, tutoriais = mais tokens
            complex_words = ["como funciona", "explique", "detalhe", "diferença entre",
                           "código", "codigo", "tutorial", "passo a passo", "me ensine"]
            if any(word in user_input.lower() for word in complex_words):
                max_tokens = 2048

            # Streaming: imprime o texto conforme o modelo gera
            # (funciona tanto para Groq/nuvem quanto para Ollama/local)
            stream_state = {"started": False}

            def stream_chunk(chunk):
                if not stream_state["started"]:
                    stream_state["started"] = True
                    clear_line()
                    sys.stdout.write("EVE: ")
                sys.stdout.write(chunk)
                sys.stdout.flush()

            # Gera resposta
            response = eve.generate_response(
                user_input,
                files=attachments,
                max_tokens=max_tokens,
                temperature=0.7,
                stream_callback=None if attachments else stream_chunk
            )

            # Extrai texto e artefatos da resposta
            response_text = response.get("text", "")
            response_artifacts = response.get("artifacts")
            model_used = response.get("model_used", "unknown")
            web_search_used = response.get("web_search_used", False)

            if stream_state["started"]:
                # Já imprimiu via streaming — só fecha a linha
                print_flush("\n")
            else:
                # Limpa a linha de "pensando..."
                clear_line()

            # VALIDA resposta antes de mostrar
            if detect_buggy_response(response_text):
                print_flush("⚠️  EVE: Ops, tive um bug! Pode reformular a pergunta? 😅\n")
                logging.error(f"Resposta bugada detectada e bloqueada: {response_text[:200]}")
                continue

            # Adiciona emoji ocasional
            if any(word in user_input.lower() for word in ["obrigado", "valeu", "legal", "massa"]):
                emojis = ["😊", "✨", "🎮"]
                if len(response_text) < 300:  # Só se resposta curta
                    response_text += " " + random.choice(emojis)

            # Determina indicador de modelo
            model_indicator = ""
            if "groq" in model_used:
                if web_search_used:
                    model_indicator = "☁️🔍"  # Nuvem + busca
                else:
                    model_indicator = "☁️"    # Só nuvem
            elif "ollama" in model_used:
                if web_search_used:
                    model_indicator = "💻🔍"  # Local + busca
                else:
                    model_indicator = "💻"    # Local

            # Se já streamou, não repete a resposta na tela
            if not stream_state["started"]:
                sys.stdout.flush()
                print_flush(f"EVE {model_indicator}: {response_text}\n")
                sys.stdout.flush()

            logging.info(f"User: {user_input}")
            if attachments:
                logging.info(f"Attachments: {len(attachments)}")
            logging.info(f"EVE: {response_text[:150]}...")

        except KeyboardInterrupt:
            print_flush("\n\nEVE: Até logo! 💜\n")
            # atexit cuidará do salvamento
            logging.info("Sessão interrompida (Ctrl+C)")
            break

        except Exception as e:
            print_flush(f"\n⚠️  Erro: {str(e)}\n")
            logging.error(f"Erro: {e}", exc_info=True)

if __name__ == "__main__":
    main()