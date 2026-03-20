# core/spell_checker.py - Sistema de Correção Ortográfica
"""
Sistema de correção ortográfica para EVE
Usa: dicionário personalizado + pyspellchecker + dicionário online
"""

import logging
import requests
import json
import os
from typing import Dict, Set, List, Optional
import re
from datetime import datetime, timedelta

logger = logging.getLogger("spell_checker")

# Tenta importar pyspellchecker (opcional)
try:
    from spellchecker import SpellChecker
    SPELLCHECKER_AVAILABLE = True
except ImportError:
    SPELLCHECKER_AVAILABLE = False
    logger.warning("pyspellchecker não disponível. Usando apenas dicionário básico.")


class OnlineDictionary:
    """
    Dicionário online usando múltiplas fontes
    """
    
    def __init__(self, cache_file: str = "dictionary_cache.json"):
        self.cache_file = cache_file
        self.cache = {}
        self.cache_expires = {}
        self.cache_duration = timedelta(days=30)  # Cache por 30 dias
        self._load_cache()
        
        # APIs disponíveis
        self.apis = {
            "dicio": "https://api.dicio.com.br/v2/search",  # Dicionário PT-BR
            "priberam": "https://dicionario.priberam.org/",  # Fallback
        }
    
    def _load_cache(self):
        """Carrega cache do disco"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get("cache", {})
                    
                    # Converte strings de data para datetime
                    expires = data.get("expires", {})
                    for word, date_str in expires.items():
                        try:
                            self.cache_expires[word] = datetime.fromisoformat(date_str)
                        except Exception:
                            pass
                    
                    logger.info(f"Cache carregado: {len(self.cache)} palavras")
            except Exception as e:
                logger.error(f"Erro ao carregar cache: {e}")
    
    def _save_cache(self):
        """Salva cache no disco"""
        try:
            # Converte datetime para string
            expires_str = {
                word: date.isoformat() 
                for word, date in self.cache_expires.items()
            }
            
            data = {
                "cache": self.cache,
                "expires": expires_str,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
    
    def _is_cache_valid(self, word: str) -> bool:
        """Verifica se cache é válido"""
        if word not in self.cache_expires:
            return False
        return datetime.now() < self.cache_expires[word]
    
    def check_word_online(self, word: str) -> bool:
        """
        Verifica se palavra existe em dicionário online
        
        Args:
            word: Palavra a verificar
            
        Returns:
            True se palavra existe
        """
        word_lower = word.lower()
        
        # Verifica cache primeiro
        if word_lower in self.cache and self._is_cache_valid(word_lower):
            return self.cache[word_lower]
        
        # Tenta APIs
        exists = self._check_dicio(word_lower)
        
        # Se não encontrou, tenta Priberam
        if not exists:
            exists = self._check_priberam(word_lower)
        
        # Salva no cache
        self.cache[word_lower] = exists
        self.cache_expires[word_lower] = datetime.now() + self.cache_duration
        
        # Salva cache a cada 10 novas palavras
        if len(self.cache) % 10 == 0:
            self._save_cache()
        
        return exists
    
    def _check_dicio(self, word: str) -> bool:
        """Verifica palavra no Dicio"""
        try:
            # API gratuita do Dicio (não oficial)
            url = f"https://www.dicio.com.br/{word}/"
            
            response = requests.get(url, timeout=3, headers={
                "User-Agent": "EVE-AI/1.0"
            })
            
            if response.status_code == 200:
                # Se página existe, palavra existe
                html = response.text
                
                # Procura por indicadores de definição
                if any(indicator in html for indicator in [
                    'class="significado"',
                    'class="adicional"',
                    '<p itemprop="description"'
                ]):
                    logger.debug(f"✅ Dicio: '{word}' encontrada")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Erro Dicio: {e}")
            return False
    
    def _check_priberam(self, word: str) -> bool:
        """Verifica palavra no Priberam (fallback)"""
        try:
            url = f"https://dicionario.priberam.org/{word}"
            
            response = requests.get(url, timeout=3, headers={
                "User-Agent": "EVE-AI/1.0"
            })
            
            if response.status_code == 200:
                html = response.text
                
                # Procura por definição
                if 'class="pb-entry-body"' in html or 'class="significado"' in html:
                    logger.debug(f"✅ Priberam: '{word}' encontrada")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Erro Priberam: {e}")
            return False
    
    def get_cache_stats(self) -> Dict:
        """Retorna estatísticas do cache"""
        valid = sum(1 for w in self.cache if self._is_cache_valid(w))
        return {
            "total_cached": len(self.cache),
            "valid_cache": valid,
            "expired_cache": len(self.cache) - valid
        }


class EVESpellChecker:
    """
    Corretor ortográfico para EVE
    """
    
    def __init__(self):
        # Dicionário de correções fixas (typos comuns do modelo)
        self.typo_fixes = {
            # Honestidade e variações
            'honetdade': 'honestidade',
            'honetsidade': 'honestidade',
            'hoenstidade': 'honestidade',
            'honestidae': 'honestidade',
            
            # Necessário
            'necesário': 'necessário',
            'necessario': 'necessário',
            'nesesario': 'necessário',
            
            # Palavras comuns duplicadas
            'possso': 'posso',
            'vocêe': 'você',
            'quee': 'que',
            'see': 'se',
            'maiss': 'mais',
            'muitoo': 'muito',
            'estee': 'este',
            'essaa': 'essa',
            
            # Erros de acentuação
            'portugues': 'português',
            'frances': 'francês',
            'ingles': 'inglês',
            'pais': 'país',
            'historico': 'histórico',
            'politica': 'política',
            'economico': 'econômico',
            
            # Erros comuns do modelo
            'tambem': 'também',
            'nao': 'não',
            'voce': 'você',
            'esta': 'está',
            'ate': 'até',
            'so': 'só',
            'ja': 'já',
            'la': 'lá',
            'ca': 'cá',
            
            # Palavras técnicas comuns
            'codigo': 'código',
            'funcao': 'função',
            'explicacao': 'explicação',
            'informacao': 'informação',
            'operacao': 'operação',
            
            # Plurais incorretos
            'informacoes': 'informações',
            'funcoes': 'funções',
            'operacoes': 'operações',
            'nacoes': 'nações',
            
            # Geografia/História
            'belgica': 'Bélgica',
            'africa': 'África',
            'europa': 'Europa',
            'america': 'América',
            'brasil': 'Brasil',
            'alemanha': 'Alemanha',
        }
        
        # Palavras corretas conhecidas (whitelist) - EXPANDIDA
        self.correct_words = {
            # Português correto
            'honestidade', 'necessário', 'português', 'história',
            'política', 'econômico', 'também', 'você', 'até',
            'função', 'código', 'informação', 'operação',

            # Geografia e História
            'Bélgica', 'África', 'Europa', 'Brasil', 'Congo',
            'Leopold', 'colonial', 'atrocidades', 'exploração',
            'independência', 'revolução', 'guerra', 'século',
            'Bretanha', 'bretanha', 'Grã-Bretanha', 'Reino', 'Unido',

            # JOGOS - Paradox Interactive + Mecânicas
            'Stellaris', 'stellaris', 'Hearts', 'Iron', 'hoi4', 'HOI4',
            'Victoria', 'victoria', 'vic3', 'VIC3',
            'Crusader', 'crusader', 'Kings', 'kings', 'ck3', 'CK3',
            'Europa', 'europa', 'Universalis', 'universalis', 'eu4', 'EU4',
            'Imperator', 'imperator', 'Rome', 'rome',
            'Paradox', 'paradox', 'DLC', 'dlc',
            # Mecânicas de jogos
            'gameplay', 'Gameplay', 'mod', 'Mod', 'mods', 'Mods',
            'buff', 'Buff', 'nerf', 'Nerf', 'patch', 'Patch',
            'speedrun', 'Speedrun', 'walkthrough', 'Walkthrough',
            'achievement', 'Achievement', 'conquista', 'conquistas',

            # Outros jogos populares
            'Minecraft', 'minecraft', 'Roblox', 'roblox',
            'Fortnite', 'fortnite', 'League', 'Legends',
            'Valorant', 'valorant', 'Overwatch', 'overwatch',
            'Cyberpunk', 'cyberpunk', 'Witcher', 'witcher',
            'Steam', 'steam', 'Epic', 'epic', 'Games', 'games',
            'PlayStation', 'playstation', 'Xbox', 'xbox', 'Nintendo', 'nintendo',
            'Skyrim', 'skyrim', 'Fallout', 'fallout', 'Elder', 'Scrolls',
            'Battlefield', 'battlefield', 'Call', 'Duty', 'duty',
            'Counter', 'Strike', 'strike', 'CS', 'CSGO', 'csgo',
            'Dota', 'dota', 'MOBA', 'moba', 'MMORPG', 'mmorpg',
            'RPG', 'rpg', 'FPS', 'fps', 'RTS', 'rts',

            # Tecnologia e Redes
            'Tor', 'tor', 'TOR', 'VPN', 'vpn',
            'onion', 'Onion', 'darknet', 'Darknet',
            'browser', 'Browser', 'Firefox', 'firefox',
            'Chrome', 'chrome', 'Safari', 'safari',

            # Programação
            'Python', 'python', 'JavaScript', 'javascript',
            'Java', 'java', 'C++', 'cpp', 'Rust', 'rust',
            'Go', 'golang', 'TypeScript', 'typescript',
            'React', 'react', 'Vue', 'vue', 'Angular', 'angular',
            'Django', 'django', 'Flask', 'flask',
            'API', 'api', 'JSON', 'json', 'XML', 'xml',
            'Git', 'git', 'GitHub', 'github', 'GitLab', 'gitlab',

            # Hardware/Software
            'Windows', 'windows', 'Linux', 'linux', 'macOS', 'macos',
            'Android', 'android', 'iOS', 'ios',
            'GPU', 'gpu', 'CPU', 'cpu', 'RAM', 'ram',
            'NVIDIA', 'nvidia', 'AMD', 'amd', 'Intel', 'intel',
        }
        
        # NOVO: Dicionário online
        self.online_dict = OnlineDictionary()
        logger.info("Dicionário online inicializado")
        
        # Inicializa spellchecker se disponível
        if SPELLCHECKER_AVAILABLE:
            try:
                self.spell = SpellChecker(language='pt')
                # Adiciona palavras customizadas
                self.spell.word_frequency.load_words(self.correct_words)
                logger.info("SpellChecker PT inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar spellchecker: {e}")
                self.spell = None
        else:
            self.spell = None
    
    def correct_word(self, word: str, use_online: bool = False) -> str:
        """
        Corrige uma palavra individual - MELHORADO para proteger nomes próprios

        Args:
            word: Palavra a corrigir
            use_online: Se deve usar dicionário online

        Returns:
            Palavra corrigida ou original
        """
        # NOVO: Proteção para palavras muito curtas (<3) ou muito longas (>25)
        if len(word) < 3 or len(word) > 25:
            return word

        word_lower = word.lower()

        # 1. Verifica dicionário de correções fixas
        if word_lower in self.typo_fixes:
            corrected = self.typo_fixes[word_lower]
            logger.debug(f"Correção fixa: '{word}' → '{corrected}'")
            return corrected

        # 2. Se está na whitelist, mantém
        if word in self.correct_words or word_lower in self.correct_words:
            return word

        # NOVO 3. Protege nomes próprios (palavras com primeira letra maiúscula)
        # Exceto se for início de frase (será tratado depois)
        if word[0].isupper() and len(word) > 3:
            # Se palavra tem maiúscula no meio (ex: iPhone, JavaScript), protege sempre
            if any(c.isupper() for c in word[1:]):
                logger.debug(f"🛡️ Protegido (CamelCase): '{word}'")
                return word
            # Se é nome próprio simples (só primeira maiúscula), adiciona à whitelist
            logger.debug(f"🛡️ Protegido (Nome próprio): '{word}'")
            self.correct_words.add(word)
            return word

        # 4. NOVO: Verifica dicionário online (DESABILITADO por padrão)
        if use_online and len(word) > 3:
            try:
                if self.online_dict.check_word_online(word_lower):
                    logger.debug(f"✅ Online: '{word}' existe")
                    # Adiciona à whitelist para próximas vezes
                    self.correct_words.add(word_lower)
                    return word
            except Exception as e:
                logger.debug(f"Erro online dict: {e}")

        # 5. Usa spellchecker se disponível (COM MAIS FILTROS)
        if self.spell and len(word) > 3:
            # Ignora palavras com números
            if any(c.isdigit() for c in word):
                return word

            # Ignora palavras ALL CAPS (siglas)
            if word.isupper() and len(word) > 1:
                return word

            # NOVO: Ignora palavras com caracteres especiais (_-@.)
            if any(c in word for c in ['_', '-', '@', '.']):
                return word

            # Verifica se está incorreta
            if word_lower not in self.spell:
                # Pega sugestão
                suggestion = self.spell.correction(word_lower)

                # NOVO: Só aceita sugestão se tiver alta confiança
                # (palavra original muito parecida com sugestão)
                if suggestion and suggestion != word_lower:
                    # Calcula similaridade (Levenshtein simplificado)
                    if len(word_lower) > 0 and len(suggestion) > 0:
                        # Se palavras são muito diferentes, não corrige
                        size_diff = abs(len(word_lower) - len(suggestion))
                        if size_diff > 3:  # Diferença de tamanho muito grande
                            logger.debug(f"⚠️ Ignorado (muito diferente): '{word}' → '{suggestion}'")
                            return word

                    logger.debug(f"Sugestão spellchecker: '{word}' → '{suggestion}'")
                    # Mantém capitalização original
                    if word[0].isupper():
                        return suggestion.capitalize()
                    return suggestion

        return word
    
    def correct_text(self, text: str, aggressive: bool = False, use_online: bool = False) -> str:
        """
        Corrige texto completo - PROTEGE nomes de jogos automaticamente

        Args:
            text: Texto a corrigir
            aggressive: Se True, usa spellchecker em todas palavras
            use_online: Se True, usa dicionário online

        Returns:
            Texto corrigido
        """
        if not text:
            return text

        # NOVO: Detecta contexto de jogos (palavras-chave que indicam que está falando de games)
        game_context_keywords = [
            'jogo', 'game', 'gameplay', 'jogador', 'player',
            'dlc', 'mod', 'patch', 'achievement', 'conquista',
            'campanha', 'multiplayer', 'single player',
            'paradox', 'steam', 'console', 'pc gaming'
        ]
        is_game_context = any(keyword in text.lower() for keyword in game_context_keywords)

        # NOVO: Detecta e protege nomes de jogos conhecidos (case-insensitive)
        game_patterns = {
            # Paradox games
            r'\b(Hearts\s+of\s+Iron\s+(?:IV|4|HOI4|hoi4))\b': 'Hearts of Iron 4',
            r'\b(Victoria\s+(?:III|3|VIC3|vic3))\b': 'Victoria 3',
            r'\b(Crusader\s+Kings\s+(?:III|3|CK3|ck3))\b': 'Crusader Kings 3',
            r'\b(Europa\s+Universalis\s+(?:IV|4|EU4|eu4))\b': 'Europa Universalis 4',
            r'\b(Imperator\s+Rome)\b': 'Imperator Rome',
            r'\bStellaris\b': 'Stellaris',

            # Popular games
            r'\b(League\s+of\s+Legends)\b': 'League of Legends',
            r'\b(Call\s+of\s+Duty)\b': 'Call of Duty',
            r'\b(Counter[- ]Strike)\b': 'Counter-Strike',
            r'\b(Grand\s+Theft\s+Auto)\b': 'Grand Theft Auto',
            r'\b(The\s+Witcher)\b': 'The Witcher',
            r'\b(Elder\s+Scrolls)\b': 'Elder Scrolls',
            r'\bMinecraft\b': 'Minecraft',
            r'\bFortnite\b': 'Fortnite',
            r'\bRoblox\b': 'Roblox',
            r'\bValorant\b': 'Valorant',
            r'\bOverwatch\b': 'Overwatch',
            r'\bCyberpunk\b': 'Cyberpunk',
            r'\bSkyrim\b': 'Skyrim',
            r'\bFallout\b': 'Fallout',
            r'\bDota\b': 'Dota',

            # Platforms
            r'\b(PlayStation)\b': 'PlayStation',
            r'\bXbox\b': 'Xbox',
            r'\bNintendo\b': 'Nintendo',
            r'\bSteam\b': 'Steam',

            # Termos técnicos que não devem ser traduzidos
            r'\b(Tor\s+(?:Browser|Network))\b': 'Tor Browser',
            r'\bVPN\b': 'VPN',
            r'\bAPI\b': 'API',
            r'\bJSON\b': 'JSON',
        }

        # Se está em contexto de jogo, adiciona proteções extras
        if is_game_context:
            logger.debug("🎮 Contexto de jogo detectado - proteções extras ativadas")
            # Protege também palavras isoladas que podem ser nomes de jogos
            extra_games = [
                'Victoria', 'Stellaris', 'Hearts', 'Iron', 'Crusader', 'Kings',
                'Europa', 'Universalis', 'Imperator', 'Rome',
                'Minecraft', 'Fortnite', 'Valorant', 'Overwatch', 'Roblox',
                'Skyrim', 'Fallout', 'Cyberpunk', 'Witcher', 'Dota'
            ]
            # Adiciona temporariamente à whitelist
            for game in extra_games:
                self.correct_words.add(game)
                self.correct_words.add(game.lower())

        # Cria mapeamento de placeholders temporários
        placeholders = {}
        protected_text = text

        # Substitui nomes de jogos por placeholders
        for pattern, correct_name in game_patterns.items():
            matches = re.finditer(pattern, protected_text, re.IGNORECASE)
            for match in matches:
                placeholder = f"__GAME_{len(placeholders)}__"
                placeholders[placeholder] = correct_name
                protected_text = protected_text.replace(match.group(0), placeholder)

        # Separa em palavras mantendo pontuação
        words = re.findall(r'\b\w+\b|\W+', protected_text)

        corrected_words = []
        for word in words:
            # Se é placeholder de jogo, mantém
            if word.startswith("__GAME_") and word.endswith("__"):
                corrected_words.append(word)
                continue

            # Se não é palavra (pontuação, espaços), mantém
            if not word.strip() or not any(c.isalpha() for c in word):
                corrected_words.append(word)
                continue

            # Corrige palavra
            if aggressive or word.lower() in self.typo_fixes:
                corrected = self.correct_word(word, use_online=use_online)
                corrected_words.append(corrected)
            else:
                # Modo conservador: só correções fixas
                if word.lower() in self.typo_fixes:
                    corrected_words.append(self.typo_fixes[word.lower()])
                else:
                    corrected_words.append(word)

        result = ''.join(corrected_words)

        # Restaura nomes de jogos protegidos
        for placeholder, game_name in placeholders.items():
            result = result.replace(placeholder, game_name)

        return result
    
    def add_word(self, word: str):
        """Adiciona palavra ao dicionário de palavras corretas"""
        self.correct_words.add(word)
        if self.spell:
            self.spell.word_frequency.load_words([word])
    
    def add_typo(self, typo: str, correct: str):
        """Adiciona correção fixa ao dicionário"""
        self.typo_fixes[typo.lower()] = correct
        logger.info(f"Correção adicionada: '{typo}' → '{correct}'")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do corretor"""
        stats = {
            "typo_fixes": len(self.typo_fixes),
            "correct_words": len(self.correct_words),
            "spellchecker_available": SPELLCHECKER_AVAILABLE,
            "spellchecker_active": self.spell is not None,
            "online_dict_available": True,
        }
        
        # Adiciona stats do cache online
        stats.update(self.online_dict.get_cache_stats())
        
        return stats


# Instância global (singleton)
_spell_checker = None

def get_spell_checker() -> EVESpellChecker:
    """Retorna instância singleton do spell checker"""
    global _spell_checker
    if _spell_checker is None:
        _spell_checker = EVESpellChecker()
    return _spell_checker