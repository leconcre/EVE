# core/web_search_tool.py - VERSÃO MELHORADA
import requests
import logging
import random
import re
import html
from typing import Optional, List, Dict
from datetime import datetime
import time

logger = logging.getLogger("web_search")
logger.setLevel(logging.INFO)

class WebSearchTool:
    """
    Ferramenta de busca web com múltiplas fontes
    ORDEM: Google → DuckDuckGo → Wikipedia PT → Wikipedia EN → SearXNG
    """
    
    def __init__(self):
        self.available = self._check_internet()
        self.last_check = datetime.now()
        logger.info(f"WebSearch inicializado. Internet: {self.available}")
    
    def _check_internet(self) -> bool:
        """Verifica conexão"""
        try:
            requests.get("https://www.google.com", timeout=2)
            return True
        except Exception:
            return False

    def search(self, query: str, max_results: int = 5) -> Dict:
        """
        Busca em múltiplas fontes com fallback automático
        CORREÇÃO: Tenta TODAS as fontes em paralelo e aceita o primeiro resultado válido
        Prioridade: Wikipedia EN > Wikipedia PT > DuckDuckGo > Google > SearXNG
        """
        # Recheck internet
        if (datetime.now() - self.last_check).seconds > 60:
            self.available = self._check_internet()
            self.last_check = datetime.now()

        if not self.available:
            return {
                "success": False,
                "error": "offline",
                "message": "Sem internet."
            }

        # CORREÇÃO: Reduzido requisito de 100 para 50 caracteres mínimos
        min_chars = 50

        # 1. WIKIPEDIA EN (PRIORIDADE MÁXIMA)
        logger.info("📚 Tentando Wikipedia EN...")
        result = self._search_wikipedia(query, lang="en")
        if result["success"] and result.get("abstract") and len(result.get("abstract", "")) > min_chars:
            logger.info("✅ Wikipedia EN retornou resultado válido")
            return result
        logger.warning("⚠️ Wikipedia EN falhou ou resultado vazio")

        # 2. Wikipedia PT
        logger.info("📚 Tentando Wikipedia PT...")
        time.sleep(0.3)
        result = self._search_wikipedia(query, lang="pt")
        if result["success"] and result.get("abstract") and len(result.get("abstract", "")) > min_chars:
            logger.info("✅ Wikipedia PT retornou resultado")
            return result
        logger.warning("⚠️ Wikipedia PT falhou")

        # 3. DuckDuckGo
        logger.info("🦆 Tentando DuckDuckGo...")
        time.sleep(0.3)
        result = self._search_duckduckgo(query)
        if result["success"] and result.get("abstract") and len(result.get("abstract", "")) > min_chars:
            logger.info("✅ DuckDuckGo retornou resultado")
            return result
        logger.warning("⚠️ DuckDuckGo falhou")

        # 4. Google
        logger.info("🔍 Tentando Google...")
        time.sleep(0.3)
        result = self._search_google(query)
        if result["success"] and result.get("abstract") and len(result.get("abstract", "")) > min_chars:
            logger.info("✅ Google retornou resultado válido")
            return result
        logger.warning("⚠️ Google falhou")

        # 5. SearXNG (último recurso, aceita resultado menor)
        logger.info("🔎 Tentando SearXNG...")
        time.sleep(0.3)
        result = self._search_alternative(query)
        if result["success"] and result.get("abstract"):  # SearXNG: aceita qualquer tamanho
            logger.info("✅ SearXNG retornou resultado")
            return result

        logger.error("❌ TODAS as 5 fontes falharam")
        return {
            "success": False,
            "error": "all_failed",
            "message": "Não encontrei informações relevantes em nenhuma fonte (Wikipedia EN, PT, DuckDuckGo, Google, SearXNG)."
        }
    
    def _search_google(self, query: str) -> Dict:
        """Busca no Google via scraping otimizado"""
        try:
            # User-Agents rotativos para evitar bloqueio
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            ]

            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }

            url = "https://www.google.com/search"
            params = {
                "q": query,
                "hl": "pt-BR",
                "num": 10,
                "gl": "br"
            }

            # Adiciona delay aleatório para parecer mais humano
            time.sleep(random.uniform(0.5, 1.5))

            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Google retornou status {response.status_code}")
                return {"success": False}
            
            page_html = response.text

            # === MÚLTIPLOS PADRÕES DE EXTRAÇÃO ===

            # Padrão 1: Featured Snippet (melhor resultado)
            featured = re.search(r'<div[^>]*class="[^"]*(?:hgKElc|kno-rdesc|LGOjhe)[^"]*"[^>]*>([^<]{80,800})</div>', page_html)
            if featured:
                text = self._clean_html_entities(featured.group(1))
                if len(text) > 80:
                    logger.info(f"✅ Google: Featured snippet ({len(text)} chars)")
                    return {
                        "success": True,
                        "query": query,
                        "abstract": text[:1000],
                        "abstract_source": "Google Featured Snippet",
                        "abstract_url": "",
                        "related_topics": []
                    }

            # Padrão 2: Knowledge Panel
            knowledge = re.search(r'<div[^>]*class="[^"]*kno-rdesc[^"]*"[^>]*><span>([^<]{80,800})</span>', page_html)
            if knowledge:
                text = self._clean_html_entities(knowledge.group(1))
                if len(text) > 80:
                    logger.info(f"✅ Google: Knowledge panel ({len(text)} chars)")
                    return {
                        "success": True,
                        "query": query,
                        "abstract": text[:1000],
                        "abstract_source": "Google Knowledge Panel",
                        "abstract_url": "",
                        "related_topics": []
                    }

            # Padrão 3: Snippets normais (múltiplos padrões)
            snippet_patterns = [
                r'<div[^>]*class="[^"]*(?:BNeawe|VwiC3b)[^"]*"[^>]*>([^<]{50,500})</div>',
                r'<span[^>]*class="[^"]*(?:aCOpRe|hgKElc)[^"]*"[^>]*>([^<]{50,500})</span>',
                r'<div[^>]*data-content-feature="[^"]*"[^>]*>([^<]{50,500})</div>',
                r'class="[^"]*st[^"]*">([^<]{50,500})<',
            ]

            snippets = []
            for pattern in snippet_patterns:
                matches = re.findall(pattern, page_html)
                snippets.extend(matches)

            if snippets:
                # Limpa e combina os melhores
                cleaned = []
                seen = set()
                for snippet in snippets[:10]:
                    text = self._clean_html_entities(snippet)
                    text_lower = text.lower()

                    # Filtra ruído
                    if (len(text) > 50 and
                        text not in seen and
                        not any(skip in text_lower for skip in ['translate this page', 'loading', 'javascript', 'cookies', 'privacy'])):
                        cleaned.append(text)
                        seen.add(text)

                if cleaned:
                    combined = " ".join(cleaned[:3])
                    logger.info(f"✅ Google: {len(cleaned)} snippets encontrados")
                    return {
                        "success": True,
                        "query": query,
                        "abstract": combined[:1200],
                        "abstract_source": "Google Search Results",
                        "abstract_url": "",
                        "related_topics": []
                    }

            # Padrão 4: Qualquer texto longo dentro de divs de resultado
            long_text = re.findall(r'<div[^>]{0,200}>([^<]{100,600})</div>', page_html)
            if long_text:
                for text in long_text[:5]:
                    cleaned = self._clean_html_entities(text)
                    if len(cleaned) > 100:
                        logger.info(f"✅ Google: Texto longo extraído ({len(cleaned)} chars)")
                        return {
                            "success": True,
                            "query": query,
                            "abstract": cleaned[:1000],
                            "abstract_source": "Google",
                            "abstract_url": "",
                            "related_topics": []
                        }

            # Última tentativa: salva HTML para debug
            logger.warning("⚠️ Google: Nenhum padrão encontrado no HTML")

            # FALLBACK 1: Tenta versão mobile do Google (menos proteções)
            logger.info("   Tentando Google Mobile...")
            mobile_result = self._search_google_mobile(query)
            if mobile_result.get("success"):
                return mobile_result

            # FALLBACK 2: Usa Google via proxy lite
            logger.info("   Tentando Google Lite...")
            return self._search_google_lite(query)

        except requests.Timeout:
            logger.error("❌ Google: Timeout")
            return {"success": False}
        except Exception as e:
            logger.error(f"❌ Google: {e}")
            return {"success": False}
    
    def _search_google_mobile(self, query: str) -> Dict:
        """Busca na versão mobile do Google (menos proteções anti-bot)"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            }

            url = "https://www.google.com/search"
            params = {
                "q": query,
                "hl": "pt-BR",
                "gl": "br",
                "ie": "UTF-8"
            }

            time.sleep(random.uniform(0.3, 0.8))
            response = requests.get(url, params=params, headers=headers, timeout=12)

            if response.status_code != 200:
                logger.warning(f"Google Mobile: status {response.status_code}")
                return {"success": False}

            page_html = response.text

            # Padrões específicos para mobile
            mobile_patterns = [
                r'<div[^>]*class="[^"]*(?:kCrYT|BNeawe)[^"]*"[^>]*>([^<]{60,600})</div>',
                r'<div[^>]*data-hveid[^>]*>([^<]{60,600})</div>',
                r'<span[^>]*>([^<]{80,600})</span>',
            ]

            for pattern in mobile_patterns:
                matches = re.findall(pattern, page_html)
                if matches:
                    cleaned = []
                    for match in matches[:5]:
                        text = self._clean_html_entities(match)
                        if len(text) > 60 and not any(skip in text.lower() for skip in ['javascript', 'cookies', 'privacy policy']):
                            cleaned.append(text)

                    if cleaned:
                        combined = " ".join(cleaned[:2])
                        logger.info(f"✅ Google Mobile: {len(cleaned)} resultados")
                        return {
                            "success": True,
                            "query": query,
                            "abstract": combined[:1000],
                            "abstract_source": "Google Mobile",
                            "abstract_url": "",
                            "related_topics": []
                        }

            return {"success": False}

        except Exception as e:
            logger.error(f"❌ Google Mobile: {e}")
            return {"success": False}

    def _search_google_lite(self, query: str) -> Dict:
        """Busca no Google Lite (versão sem JavaScript, mais difícil de bloquear)"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
            }

            # Google Lite endpoint (sem JS)
            url = "https://www.google.com/search"
            params = {
                "q": query,
                "gbv": "1",  # Google Basic Version (sem JavaScript)
                "sei": "".join(random.choices("0123456789ABCDEFabcdef", k=16))
            }

            time.sleep(random.uniform(0.4, 1.0))
            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                return {"success": False}

            page_html = response.text

            # Extrai qualquer texto entre tags que pareça um resultado
            # Versão lite tem HTML muito mais simples
            text_blocks = re.findall(r'<p[^>]*>([^<]{80,800})</p>', page_html)
            text_blocks.extend(re.findall(r'<div[^>]*>([^<]{100,800})</div>', page_html))
            text_blocks.extend(re.findall(r'<td[^>]*>([^<]{80,600})</td>', page_html))

            if text_blocks:
                cleaned = []
                seen = set()
                for block in text_blocks:
                    text = self._clean_html_entities(block)
                    text_normalized = text.lower().strip()

                    if (len(text) > 80 and
                        text_normalized not in seen and
                        not any(skip in text_normalized for skip in [
                            'google', 'search', 'cookie', 'privacy', 'about', 'settings',
                            'sign in', 'images', 'maps', 'translate'
                        ])):
                        cleaned.append(text)
                        seen.add(text_normalized)
                        if len(cleaned) >= 2:
                            break

                if cleaned:
                    combined = " ".join(cleaned)
                    logger.info(f"✅ Google Lite: {len(cleaned)} blocos extraídos")
                    return {
                        "success": True,
                        "query": query,
                        "abstract": combined[:1000],
                        "abstract_source": "Google Lite",
                        "abstract_url": "",
                        "related_topics": []
                    }

            return {"success": False}

        except Exception as e:
            logger.error(f"❌ Google Lite: {e}")
            return {"success": False}

    def _clean_html_entities(self, text: str) -> str:
        """Limpa entidades HTML"""
        text = html.unescape(text)
        text = text.replace("&quot;", '"').replace("&amp;", "&")
        text = text.replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
        # Remove tags HTML restantes
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    
    def _search_duckduckgo(self, query: str) -> Dict:
        """Busca no DuckDuckGo com retry e HTML scraping como fallback"""
        # Primeiro tenta a API oficial
        for attempt in range(2):
            try:
                url = "https://api.duckduckgo.com/"
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1
                }

                user_agents = [
                    "EVE-AI/1.0 (Educational Assistant)",
                    "Mozilla/5.0 (compatible; EVE-Bot/1.0; +http://eve-ai.com)",
                ]

                headers = {
                    "User-Agent": random.choice(user_agents)
                }

                time.sleep(random.uniform(0.3, 0.8))
                response = requests.get(url, params=params, headers=headers, timeout=10)
                
                if response.status_code == 202 and attempt == 0:
                    time.sleep(2)
                    continue
                
                if response.status_code != 200:
                    return {"success": False}
                
                data = response.json()
                
                results = {
                    "success": True,
                    "query": query,
                    "abstract": data.get("Abstract", ""),
                    "abstract_source": data.get("AbstractSource", ""),
                    "abstract_url": data.get("AbstractURL", ""),
                    "related_topics": []
                }
                
                for topic in data.get("RelatedTopics", [])[:5]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results["related_topics"].append({
                            "text": topic.get("Text", ""),
                            "url": topic.get("FirstURL", "")
                        })
                
                # Se API retornou resultado válido
                if results["abstract"] or results["related_topics"]:
                    return results

                # Se API não retornou nada, tenta scraping HTML
                if attempt == 1:
                    logger.info("   API vazia, tentando scraping HTML...")
                    return self._search_duckduckgo_html(query)

            except Exception as e:
                logger.error(f"❌ DuckDuckGo API: {e}")
                if attempt == 0:
                    continue

        # Fallback final: scraping HTML
        logger.info("   Tentando scraping HTML como fallback...")
        return self._search_duckduckgo_html(query)

    def _search_duckduckgo_html(self, query: str) -> Dict:
        """Scraping HTML do DuckDuckGo como fallback"""
        try:
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]

            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            url = "https://html.duckduckgo.com/html/"
            data = {"q": query}

            time.sleep(random.uniform(0.5, 1.0))
            response = requests.post(url, data=data, headers=headers, timeout=10)

            if response.status_code != 200:
                return {"success": False}

            page_html = response.text

            # Extrai snippet do primeiro resultado
            snippet_match = re.search(r'class="result__snippet">([^<]{80,500})</a>', page_html)
            if snippet_match:
                text = self._clean_html_entities(snippet_match.group(1))
                logger.info(f"✅ DuckDuckGo HTML: Encontrou snippet ({len(text)} chars)")
                return {
                    "success": True,
                    "query": query,
                    "abstract": text,
                    "abstract_source": "DuckDuckGo",
                    "abstract_url": "",
                    "related_topics": []
                }

            return {"success": False}

        except Exception as e:
            logger.error(f"❌ DuckDuckGo HTML: {e}")
            return {"success": False}
    
    def _search_wikipedia(self, query: str, lang: str = "pt") -> Dict:
        """Busca na Wikipedia com artigo completo filtrado"""
        try:
            base_url = f"https://{lang}.wikipedia.org/w/api.php"
            
            # Busca artigo
            search_params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "utf8": 1,
                "srlimit": 1
            }
            
            headers = {
                "User-Agent": "EVE-AI/1.0 (Educational Assistant)"
            }
            
            response = requests.get(base_url, params=search_params, headers=headers, timeout=8)
            
            if response.status_code != 200:
                return {"success": False}
            
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            
            if not search_results:
                return {"success": False}
            
            page_title = search_results[0].get("title", "")
            
            # Busca conteúdo completo
            extract_params = {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "titles": page_title,
                "exintro": False,
                "explaintext": True,
                "utf8": 1
            }
            
            response = requests.get(base_url, params=extract_params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {"success": False}
            
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            page = next(iter(pages.values()), {})
            full_text = page.get("extract", "")
            
            if not full_text or len(full_text) < 100:
                return {"success": False}
            
            # Extrai parágrafos relevantes
            relevant = self._extract_relevant_paragraphs(full_text, query)
            
            wiki_lang = f"{lang}.wikipedia.org"
            
            return {
                "success": True,
                "query": query,
                "abstract": relevant,
                "abstract_source": f"Wikipedia ({lang.upper()})",
                "abstract_url": f"https://{wiki_lang}/wiki/{page_title.replace(' ', '_')}",
                "related_topics": []
            }
            
        except Exception as e:
            logger.error(f"❌ Wikipedia: {e}")
            return {"success": False}
    
    def _extract_relevant_paragraphs(self, full_text: str, query: str, max_chars: int = 1500) -> str:
        """Extrai parágrafos relevantes"""
        paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 50]
        
        query_words = set(query.lower().split())
        
        scored = []
        for i, para in enumerate(paragraphs[:20]):
            para_lower = para.lower()
            score = sum(1 for word in query_words if word in para_lower)

            if i < 3:
                score += 2

            scored.append((score, para))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        
        result_paragraphs = []
        total_chars = 0
        
        for score, para in scored[:5]:
            if score > 0 and total_chars + len(para) < max_chars:
                result_paragraphs.append(para)
                total_chars += len(para)
        
        if not result_paragraphs and paragraphs:
            return paragraphs[0][:1000]
        
        return '\n\n'.join(result_paragraphs[:3])
    
    def _search_alternative(self, query: str) -> Dict:
        """SearXNG como último recurso"""
        try:
            url = "https://searx.be/search"
            params = {
                "q": query,
                "format": "json",
                "language": "pt"
            }
            
            headers = {
                "User-Agent": "EVE-AI/1.0"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {"success": False}
            
            data = response.json()
            results_list = data.get("results", [])
            
            if not results_list:
                return {"success": False}
            
            first = results_list[0]
            
            return {
                "success": True,
                "query": query,
                "abstract": first.get("content", "")[:600],
                "abstract_source": "Web Search (SearXNG)",
                "abstract_url": first.get("url", ""),
                "related_topics": [
                    {
                        "text": r.get("content", "")[:250],
                        "url": r.get("url", "")
                    }
                    for r in results_list[1:4]
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ SearXNG: {e}")
            return {"success": False}
    
    def search_formatted(self, query: str) -> str:
        """Busca e retorna formatado"""
        result = self.search(query)
        
        if not result["success"]:
            if result.get("error") == "offline":
                return "[OFFLINE] Sem internet."
            else:
                return f"[ERRO] {result.get('message', 'Busca falhou')}"
        
        parts = []
        
        if result.get("abstract"):
            abstract = result["abstract"]
            abstract = html.unescape(abstract)
            abstract = re.sub(r'<[^>]+>', '', abstract)
            abstract = abstract.strip()

            if len(abstract) > 30:
                parts.append("INFORMAÇÃO ENCONTRADA:")
                parts.append(abstract[:1000])

                if result.get("abstract_source"):
                    parts.append(f"\nFonte: {result['abstract_source']}")

        if result.get("related_topics"):
            parts.append("\nINFORMAÇÕES ADICIONAIS:")
            for i, topic in enumerate(result["related_topics"][:3], 1):
                text = topic.get('text', '')
                text = html.unescape(text)
                text = re.sub(r'<[^>]+>', '', text)
                text = text.strip()
                
                if len(text) > 20:
                    parts.append(f"{i}. {text[:300]}")
        
        if not parts:
            return "[SEM RESULTADOS] Nenhuma informação encontrada."
        
        return "\n".join(parts)


class TranslationTool:
    """Tradução usando LibreTranslate"""
    
    def __init__(self, api_url: str = "https://libretranslate.de/translate"):
        self.api_url = api_url
        self.available = self._check_availability()
        logger.info(f"Translation inicializado. Disponível: {self.available}")
    
    def _check_availability(self) -> bool:
        try:
            requests.get("https://libretranslate.de/", timeout=2)
            return True
        except Exception:
            return False

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "pt") -> Dict:
        if not self.available:
            return {
                "success": False,
                "error": "offline",
                "message": "Tradução indisponível."
            }
        
        try:
            payload = {
                "q": text,
                "source": source_lang,
                "target": target_lang,
                "format": "text"
            }
            
            response = requests.post(self.api_url, json=payload, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": "api_error",
                    "message": "Erro ao traduzir."
                }
            
            data = response.json()
            
            return {
                "success": True,
                "original": text,
                "translated": data.get("translatedText", text),
                "detected_lang": data.get("detectedLanguage", {}).get("language", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Erro tradução: {e}")
            return {
                "success": False,
                "error": "exception",
                "message": str(e)
            }
    
    def translate_if_needed(self, text: str) -> str:
        """Traduz se texto em inglês"""
        english_words = ['the', 'and', 'is', 'are', 'to', 'in', 'of', 'for', 'with']
        text_lower = text.lower()
        english_count = sum(1 for word in english_words if f' {word} ' in f' {text_lower} ')
        
        if english_count >= 3:
            result = self.translate(text, source_lang="en", target_lang="pt")
            if result["success"]:
                return result["translated"]
        
        return text