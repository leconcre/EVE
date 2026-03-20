# core/memory_manager.py
from __future__ import annotations
import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


logger = logging.getLogger("memory_manager")
logger.setLevel(logging.INFO)

class MemoryManager:
    """
    Sistema de memória inteligente da EVE:
    - Armazena conversas com timestamps
    - Detecta informações importantes automaticamente
    - Recupera memórias relevantes por contexto
    - Sistema de relevância por categorias
    """

    def __init__(self, persistence_file: str = "eve_memory.json"):
        self.persistence_file = persistence_file
        self.memory: List[Dict[str, Any]] = []
        self.important_facts: Dict[str, Any] = {}  # Fatos importantes extraídos
        self.response_cache: Dict[str, Dict[str, Any]] = {}  # Cache de respostas frequentes
        self.cache_hits = 0
        self.cache_misses = 0
        self._last_save_time = 0.0
        self._save_interval = 5.0  # Salva no máximo a cada 5 segundos
        self._dirty = False

        self._load_memory()

    def _load_memory(self):
        """Carrega memória do arquivo JSON"""
        if os.path.isfile(self.persistence_file):
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memory = data.get("memory", [])
                    self.important_facts = data.get("important_facts", {})
                    self.response_cache = data.get("response_cache", {})

                    # Limpa memórias muito antigas (mais de 30 dias)
                    self._cleanup_old_memories()
                    # Limpa cache expirado
                    self._cleanup_expired_cache()

                    logger.info(f"Memória carregada: {len(self.memory)} entradas, {len(self.important_facts)} fatos, {len(self.response_cache)} cache")
            except Exception as e:
                logger.error(f"Erro ao carregar memória: {e}")
                self.memory = []
                self.important_facts = {}
                self.response_cache = {}

    def _cleanup_old_memories(self):
        """Remove memórias antigas demais (mantém últimos 30 dias)"""
        cutoff_time = time.time() - (30 * 24 * 60 * 60)  # 30 dias
        original_count = len(self.memory)

        self.memory = [m for m in self.memory if m.get("timestamp", 0) > cutoff_time]

        removed = original_count - len(self.memory)
        if removed > 0:
            logger.info(f"Limpeza: {removed} memórias antigas removidas")

    def _cleanup_expired_cache(self):
        """Remove cache expirado (mantém 7 dias)"""
        cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7 dias
        original_count = len(self.response_cache)

        self.response_cache = {
            k: v for k, v in self.response_cache.items()
            if v.get("timestamp", 0) > cutoff_time
        }

        removed = original_count - len(self.response_cache)
        if removed > 0:
            logger.info(f"Cache: {removed} entradas expiradas removidas")

    def _save_memory(self, force: bool = False):
        """Salva memória no arquivo JSON (com debounce de 5s)"""
        now = time.time()
        if not force and (now - self._last_save_time) < self._save_interval:
            self._dirty = True
            return
        try:
            self._dirty = False
            self._last_save_time = now
            os.makedirs(os.path.dirname(self.persistence_file) or ".", exist_ok=True)

            data = {
                "memory": self.memory[-100:],  # Mantém últimas 100
                "important_facts": self.important_facts,
                "response_cache": self.response_cache,
                "cache_stats": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": f"{(self.cache_hits / max(self.cache_hits + self.cache_misses, 1) * 100):.1f}%"
                },
                "last_updated": datetime.now().isoformat()
            }

            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar memória: {e}")

    def _extract_important_info(self, text: str) -> Dict[str, Any]:
        """
        Detecta informações importantes no texto usando padrões.
        
        Returns:
            Dict com categoria e informação extraída
        """
        # Remove prefixos como [MODO CÓDIGO] para análise
        clean_text = text
        if clean_text.strip().startswith("["):
            end_bracket_index = clean_text.find("]")
            if end_bracket_index != -1:
                clean_text = clean_text[end_bracket_index + 1:].strip()

        text_lower = clean_text.lower()
        important = {}
        
        # Padrões de informações importantes
        patterns = {
            "nome": ["meu nome é", "me chamo", "sou o", "sou a"],
            "jogo_favorito": ["meu jogo favorito é", "adoro jogar", "estou jogando"],
            "linguagem": ["programo em", "uso python", "trabalho com", "desenvolvendo em", "em javascript", "em java"],
            "interesse": ["gosto de", "tenho interesse em", "curto muito", "adoro"],
            "projeto": ["estou fazendo um", "trabalhando em um", "criando um", "desenvolvendo um", "criar um"],
            "codigo": ["código para", "codigo para", "código de", "codigo de", "um código", "um codigo"],
            "problema": ["não consigo", "estou com dificuldade em", "deu erro em", "está com bug", "um bug em"],
        }
        
        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Extrai a frase completa
                    start_idx = text_lower.find(keyword) # Usa o texto limpo para encontrar a frase
                    end_idx = clean_text.find(".", start_idx)
                    if end_idx == -1:
                        end_idx = len(clean_text)
                    
                    sentence = clean_text[start_idx:end_idx].strip()
                    important[category] = sentence
                    break
        
        return important

    def add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Adiciona uma entrada de memória com detecção automática de importância.
        
        Args:
            text: Texto da entrada (pergunta do usuário)
            metadata: Metadados (geralmente a resposta da EVE)
        """
        # Extrai informações importantes
        important_info = self._extract_important_info(text)
        
        # Atualiza fatos importantes
        for category, info in important_info.items():
            if category not in self.important_facts:
                self.important_facts[category] = []
            self.important_facts[category].append({
                "info": info,
                "timestamp": time.time(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            logger.info(f"Fato importante detectado [{category}]: {info[:50]}...")

        # Adiciona à memória
        entry = {
            "text": text,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "important": len(important_info) > 0,
            "categories": list(important_info.keys())
        }
        
        self.memory.append(entry)
        
        # Mantém apenas últimas 500 entradas (otimização)
        if len(self.memory) > 500:
            self.memory = self.memory[-500:]
        
        self._save_memory()

    def force_save(self):
        """Força o salvamento da memória no arquivo."""
        logger.info("Forçando salvamento da memória em disco...")
        self._save_memory(force=True)

    def get_relevant_context(self, query: str, top_k: int = 5) -> List[str]:
        """
        Retorna os top_k textos mais relevantes para a query.
        
        Args:
            query: Query de busca
            top_k: Número de resultados
            
        Returns:
            Lista de textos relevantes
        """
        if not self.memory:
            return []
        
        query_lower = query.lower()
        scored_memories = []
        
        for entry in self.memory:
            score = 0
            text = entry["text"].lower()
            
            # Score por palavras-chave
            words = query_lower.split()
            for word in words:
                if len(word) > 3 and word in text:
                    score += 2
            
            # Bonus se for marcado como importante
            if entry.get("important"):
                score += 3
            
            # Bonus por recência (últimas 24h)
            if time.time() - entry["timestamp"] < 86400:
                score += 1
            
            if score > 0:
                scored_memories.append((score, entry["text"]))
        
        # Ordena por score
        scored_memories.sort(reverse=True, key=lambda x: x[0])
        
        return [text for score, text in scored_memories[:top_k]]

    def get_important_facts(self, category: Optional[str] = None) -> Dict[str, List]:
        """
        Retorna fatos importantes, opcionalmente filtrados por categoria.
        
        Args:
            category: Categoria específica (ex: "nome", "jogo_favorito")
            
        Returns:
            Dict com fatos importantes
        """
        if category:
            return {category: self.important_facts.get(category, [])}
        return self.important_facts

    def get_context_summary(self) -> str:
        """
        Gera um resumo do contexto importante para incluir no prompt.
        
        Returns:
            String com resumo contextual
        """
        summary_parts = []
        
        # Adiciona fatos importantes recentes
        for category, facts in self.important_facts.items():
            if facts:
                # Pega o mais recente de cada categoria
                latest = max(facts, key=lambda x: x["timestamp"])
                summary_parts.append(f"- {latest['info']}")
        
        if summary_parts:
            return "Contexto importante:\n" + "\n".join(summary_parts[-5:])  # Últimos 5
        
        return ""

    def get_last_n(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Retorna as últimas N entradas de memória.
        
        Args:
            n: Número de entradas
            
        Returns:
            Lista de entradas
        """
        return self.memory[-n:] if self.memory else []

    def clear_memory(self):
        """Limpa toda a memória"""
        self.memory = []
        self.important_facts = {}
        self._save_memory()
        logger.info("Memória completamente limpa")

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da memória"""
        hit_rate = (self.cache_hits / max(self.cache_hits + self.cache_misses, 1)) * 100

        # Garante que important_facts é um dict (compatibilidade com formato antigo)
        if isinstance(self.important_facts, list):
            self.important_facts = {}

        return {
            "total_entries": len(self.memory),
            "important_entries": sum(1 for m in self.memory if m.get("important")),
            "important_facts": len(self.important_facts),
            "cached_responses": len(self.response_cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "categories": list(self.important_facts.keys()),
            "oldest_entry": datetime.fromtimestamp(self.memory[0]["timestamp"]).strftime("%Y-%m-%d") if self.memory else None,
            "newest_entry": datetime.fromtimestamp(self.memory[-1]["timestamp"]).strftime("%Y-%m-%d") if self.memory else None,
        }

    def get_cached_response(self, prompt: str) -> Optional[str]:
        """
        Busca resposta em cache para perguntas frequentes.

        Args:
            prompt: Pergunta do usuário

        Returns:
            Resposta em cache ou None
        """
        # Normaliza prompt para matching
        normalized = prompt.lower().strip()

        # Perguntas comuns que devem ser cacheadas
        common_questions = {
            "oi": "Oi! Como posso ajudar você hoje?",
            "olá": "Olá! Em que posso ajudar?",
            "ola": "Olá! Em que posso ajudar?",
            "tudo bem": "Tudo ótimo! E com você?",
            "como vai": "Vou bem, obrigada! Como posso ajudar?",
            "quem é você": "Sou EVE, sua assistente de IA! Posso ajudar com programação, pesquisas e conversas.",
            "o que você faz": "Sou uma assistente de IA que pode ajudar com programação, pesquisas na web, análise de imagens e muito mais!",
        }

        # Verifica respostas comuns hardcoded
        if normalized in common_questions:
            self.cache_hits += 1
            logger.debug(f"Cache HIT (hardcoded): {normalized}")
            return common_questions[normalized]

        # Verifica cache dinâmico
        if normalized in self.response_cache:
            cached = self.response_cache[normalized]
            # Verifica se não expirou (7 dias)
            if time.time() - cached.get("timestamp", 0) < (7 * 24 * 60 * 60):
                self.cache_hits += 1
                logger.debug(f"Cache HIT: {normalized[:50]}")
                return cached.get("response")

        self.cache_misses += 1
        return None

    def cache_response(self, prompt: str, response: str):
        """
        Armazena resposta em cache.

        Args:
            prompt: Pergunta
            response: Resposta gerada
        """
        normalized = prompt.lower().strip()

        # Só cacheia se:
        # 1. Não for muito longa (< 200 chars)
        # 2. Não tiver busca web
        # 3. For pergunta comum
        if len(normalized) < 200 and "[INFORMAÇÃO DA WEB]" not in response:
            self.response_cache[normalized] = {
                "response": response,
                "timestamp": time.time(),
                "uses": self.response_cache.get(normalized, {}).get("uses", 0) + 1
            }

            # Limita cache a 50 entradas (mantém mais usadas)
            if len(self.response_cache) > 50:
                # Remove menos usadas
                sorted_cache = sorted(
                    self.response_cache.items(),
                    key=lambda x: x[1].get("uses", 0)
                )
                self.response_cache = dict(sorted_cache[-50:])

            logger.debug(f"Cache SAVE: {normalized[:50]}")

    def __len__(self):
        return len(self.memory)

    def __repr__(self):
        return f"MemoryManager(entries={len(self.memory)}, important_facts={len(self.important_facts)})"