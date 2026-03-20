# core/context.py
"""
Sistema de contexto da EVE.
Separa fontes de contexto (dados passivos) de ferramentas (ações ativas).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Any, Optional, Callable
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from .feature_flags import FLAGS


class ContextSource(Enum):
    """
    Fontes de contexto (dados passivos).
    Informações já disponíveis que não requerem ação externa.
    """
    NONE = auto()                # Sem contexto necessário
    SHORT_TERM = auto()          # Buffer recente (últimas mensagens)
    LONG_TERM = auto()           # Fatos persistidos
    SUMMARY = auto()             # Contexto resumido da conversa
    PREFERENCES = auto()         # Preferências do usuário
    SESSION = auto()             # Estado da sessão atual
    FILE_CONTENT = auto()        # Conteúdo de arquivos já lidos
    PERSONALITY = auto()         # Personalidade da EVE


class ToolType(Enum):
    """
    Ferramentas que precisam ser EXECUTADAS (ações ativas).
    Operações que buscam ou modificam dados externos.
    """
    NONE = auto()                # Nenhuma ferramenta
    WEB_SEARCH = auto()          # Busca na web
    FILE_READ = auto()           # Ler arquivo do disco
    FILE_WRITE = auto()          # Escrever arquivo
    FILE_LIST = auto()           # Listar arquivos
    SCREENSHOT = auto()          # Capturar tela
    CLIPBOARD_READ = auto()      # Ler clipboard
    CLIPBOARD_WRITE = auto()     # Escrever clipboard
    SHELL_EXEC = auto()          # Executar comando shell
    CODE_EXEC = auto()           # Executar código
    API_CALL = auto()            # Chamada a API externa


@dataclass
class ToolParams:
    """Parâmetros para execução de uma ferramenta"""
    tool_type: ToolType
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000
    required: bool = False       # Se True, falha bloqueia execução

    def __repr__(self):
        return f"ToolParams({self.tool_type.name}, params={list(self.params.keys())})"


@dataclass
class ContextRequirement:
    """
    Requisitos de contexto para uma decisão.
    Separa o que já temos (sources) do que precisamos buscar (tools).
    """
    # === Fontes de contexto (passivo - já temos) ===
    sources: List[ContextSource] = field(default_factory=list)
    source_queries: Dict[ContextSource, str] = field(default_factory=dict)

    # === Ferramentas necessárias (ativo - precisamos executar) ===
    tools: List[ToolParams] = field(default_factory=list)

    # === Configuração de execução ===
    tools_required: bool = False   # Se True, não prosseguir sem as tools
    parallel_tools: bool = True    # Se True, executar tools em paralelo
    max_context_tokens: int = 4000 # Limite de tokens de contexto

    def add_source(self, source: ContextSource, query: str = None):
        """Adiciona fonte de contexto"""
        if source not in self.sources:
            self.sources.append(source)
        if query:
            self.source_queries[source] = query

    def add_tool(
        self,
        tool_type: ToolType,
        params: Dict[str, Any] = None,
        required: bool = False,
        timeout_ms: int = 30000
    ):
        """Adiciona ferramenta necessária"""
        tool = ToolParams(
            tool_type=tool_type,
            params=params or {},
            timeout_ms=timeout_ms,
            required=required
        )
        self.tools.append(tool)

    def has_tool(self, tool_type: ToolType) -> bool:
        """Verifica se tem uma ferramenta específica"""
        return any(t.tool_type == tool_type for t in self.tools)

    def get_tool_params(self, tool_type: ToolType) -> Optional[Dict]:
        """Retorna parâmetros de uma ferramenta"""
        for tool in self.tools:
            if tool.tool_type == tool_type:
                return tool.params
        return None


@dataclass
class ToolResult:
    """Resultado da execução de uma ferramenta"""
    tool_type: ToolType
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class ContextResult:
    """Resultado completo da coleta de contexto"""
    # Dados coletados por fonte
    from_sources: Dict[ContextSource, Any] = field(default_factory=dict)

    # Resultados das ferramentas
    from_tools: Dict[ToolType, ToolResult] = field(default_factory=dict)

    # Métricas
    total_tokens_estimate: int = 0
    collection_time_ms: int = 0
    tools_failed: List[ToolType] = field(default_factory=list)

    def get_source_data(self, source: ContextSource) -> Any:
        """Retorna dados de uma fonte"""
        return self.from_sources.get(source)

    def get_tool_data(self, tool_type: ToolType) -> Any:
        """Retorna dados de uma ferramenta (se sucesso)"""
        result = self.from_tools.get(tool_type)
        if result and result.success:
            return result.data
        return None

    def has_failures(self) -> bool:
        """Verifica se houve falhas"""
        return len(self.tools_failed) > 0

    def to_prompt_context(self) -> str:
        """Converte contexto para string de prompt"""
        parts = []

        # Adicionar dados das fontes
        for source, data in self.from_sources.items():
            if data:
                if source == ContextSource.SHORT_TERM:
                    parts.append(self._format_short_term(data))
                elif source == ContextSource.SUMMARY:
                    parts.append(f"[Contexto Resumido]\n{data}")
                elif source == ContextSource.PREFERENCES:
                    parts.append(f"[Preferências do Usuário]\n{self._format_dict(data)}")
                elif source == ContextSource.LONG_TERM:
                    parts.append(f"[Informações Relevantes]\n{self._format_list(data)}")

        # Adicionar dados das ferramentas
        for tool_type, result in self.from_tools.items():
            if result.success and result.data:
                if tool_type == ToolType.WEB_SEARCH:
                    parts.append(f"[Resultado da Pesquisa Web]\n{result.data}")
                elif tool_type == ToolType.FILE_READ:
                    parts.append(f"[Conteúdo do Arquivo]\n{result.data}")

        return "\n\n".join(parts)

    def _format_short_term(self, messages: List[Dict]) -> str:
        """Formata mensagens recentes"""
        if not messages:
            return ""
        lines = ["[Conversa Recente]"]
        for msg in messages[-5:]:  # Últimas 5
            user = msg.get('user', '')[:200]
            lines.append(f"Usuário: {user}")
        return "\n".join(lines)

    def _format_dict(self, d: Dict) -> str:
        """Formata dicionário"""
        return "\n".join(f"- {k}: {v}" for k, v in d.items())

    def _format_list(self, items: List) -> str:
        """Formata lista"""
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items[:10])


class ContextExecutor:
    """
    Executor de coleta de contexto.
    Coleta dados de fontes e executa ferramentas.
    """

    def __init__(self, memory=None, tool_handlers: Dict[ToolType, Callable] = None):
        """
        Args:
            memory: Instância do sistema de memória
            tool_handlers: Dict de ToolType -> função que executa a tool
        """
        self.memory = memory
        self.tool_handlers = tool_handlers or {}
        self._executor = ThreadPoolExecutor(max_workers=4)

    def close(self):
        """Libera recursos do executor"""
        self._executor.shutdown(wait=False)

    def __del__(self):
        self.close()

    def register_tool_handler(self, tool_type: ToolType, handler: Callable):
        """Registra handler para uma ferramenta"""
        self.tool_handlers[tool_type] = handler

    def collect(self, requirement: ContextRequirement) -> ContextResult:
        """
        Coleta contexto de todas as fontes e executa tools.
        Versão síncrona.
        """
        start_time = time.time()
        result = ContextResult()

        # 1. Coletar de sources (síncrono, rápido)
        for source in requirement.sources:
            query = requirement.source_queries.get(source)
            try:
                data = self._collect_source(source, query)
                if data:
                    result.from_sources[source] = data
            except Exception as e:
                if FLAGS.DEBUG_CONTEXT_COLLECTION:
                    print(f"[Context] Erro ao coletar {source.name}: {e}")

        # 2. Executar tools
        if requirement.tools:
            if requirement.parallel_tools and len(requirement.tools) > 1:
                tool_results = self._execute_tools_parallel(requirement.tools)
            else:
                tool_results = self._execute_tools_sequential(requirement.tools)

            for tool_type, tool_result in tool_results.items():
                result.from_tools[tool_type] = tool_result
                if not tool_result.success:
                    result.tools_failed.append(tool_type)

        # 3. Calcular métricas
        result.collection_time_ms = int((time.time() - start_time) * 1000)
        result.total_tokens_estimate = self._estimate_tokens(result)

        if FLAGS.DEBUG_CONTEXT_COLLECTION:
            print(f"[Context] Coletado em {result.collection_time_ms}ms")
            print(f"[Context] Sources: {list(result.from_sources.keys())}")
            print(f"[Context] Tools: {list(result.from_tools.keys())}")
            print(f"[Context] Falhas: {result.tools_failed}")

        return result

    async def collect_async(self, requirement: ContextRequirement) -> ContextResult:
        """
        Coleta contexto de forma assíncrona.
        """
        start_time = time.time()
        result = ContextResult()

        # 1. Coletar de sources
        for source in requirement.sources:
            query = requirement.source_queries.get(source)
            try:
                data = self._collect_source(source, query)
                if data:
                    result.from_sources[source] = data
            except Exception as e:
                if FLAGS.DEBUG_CONTEXT_COLLECTION:
                    print(f"[Context] Erro ao coletar {source.name}: {e}")

        # 2. Executar tools em paralelo (async)
        if requirement.tools:
            tasks = []
            for tool_params in requirement.tools:
                task = asyncio.create_task(
                    self._execute_tool_async(tool_params)
                )
                tasks.append((tool_params.tool_type, task))

            for tool_type, task in tasks:
                try:
                    tool_result = await task
                    result.from_tools[tool_type] = tool_result
                    if not tool_result.success:
                        result.tools_failed.append(tool_type)
                except Exception as e:
                    result.from_tools[tool_type] = ToolResult(
                        tool_type=tool_type,
                        success=False,
                        error=str(e)
                    )
                    result.tools_failed.append(tool_type)

        result.collection_time_ms = int((time.time() - start_time) * 1000)
        result.total_tokens_estimate = self._estimate_tokens(result)

        return result

    def _collect_source(self, source: ContextSource, query: Optional[str]) -> Any:
        """Coleta de uma fonte específica"""
        if self.memory is None:
            return None

        if source == ContextSource.SHORT_TERM:
            return self.memory.get_short_term()

        elif source == ContextSource.LONG_TERM:
            if query:
                return self.memory.search_long_term(query)
            return self.memory.get_important_facts()

        elif source == ContextSource.SUMMARY:
            return self.memory.get_summary()

        elif source == ContextSource.PREFERENCES:
            return self.memory.get_preferences()

        elif source == ContextSource.SESSION:
            return self.memory.get_session_state()

        return None

    def _execute_tools_parallel(
        self,
        tools: List[ToolParams]
    ) -> Dict[ToolType, ToolResult]:
        """Executa ferramentas em paralelo"""
        results = {}
        futures = {}

        for tool_params in tools:
            future = self._executor.submit(
                self._execute_tool,
                tool_params
            )
            futures[future] = tool_params.tool_type

        for future in as_completed(futures):
            tool_type = futures[future]
            try:
                result = future.result()
                results[tool_type] = result
            except Exception as e:
                results[tool_type] = ToolResult(
                    tool_type=tool_type,
                    success=False,
                    error=str(e)
                )

        return results

    def _execute_tools_sequential(
        self,
        tools: List[ToolParams]
    ) -> Dict[ToolType, ToolResult]:
        """Executa ferramentas sequencialmente"""
        results = {}

        for tool_params in tools:
            result = self._execute_tool(tool_params)
            results[tool_params.tool_type] = result

        return results

    def _execute_tool(self, tool_params: ToolParams) -> ToolResult:
        """Executa uma ferramenta específica"""
        start_time = time.time()
        tool_type = tool_params.tool_type

        handler = self.tool_handlers.get(tool_type)
        if not handler:
            return ToolResult(
                tool_type=tool_type,
                success=False,
                error=f"Handler não registrado para: {tool_type.name}"
            )

        try:
            data = handler(**tool_params.params)
            execution_time = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool_type=tool_type,
                success=True,
                data=data,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_type=tool_type,
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )

    async def _execute_tool_async(self, tool_params: ToolParams) -> ToolResult:
        """Executa ferramenta de forma assíncrona"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._execute_tool,
            tool_params
        )

    def _estimate_tokens(self, result: ContextResult) -> int:
        """Estima número de tokens no contexto"""
        total = 0

        for data in result.from_sources.values():
            if isinstance(data, str):
                total += len(data) // 4  # Aproximação
            elif isinstance(data, list):
                total += sum(len(str(item)) // 4 for item in data)
            elif isinstance(data, dict):
                total += len(str(data)) // 4

        for tool_result in result.from_tools.values():
            if tool_result.success and tool_result.data:
                if isinstance(tool_result.data, str):
                    total += len(tool_result.data) // 4
                else:
                    total += len(str(tool_result.data)) // 4

        return total


# =============================================================================
# BUILDERS DE CONTEXTO
# =============================================================================

class ContextBuilder:
    """Builder para criar ContextRequirement de forma fluente"""

    def __init__(self):
        self._requirement = ContextRequirement()

    def with_short_term(self) -> 'ContextBuilder':
        """Adiciona buffer de curto prazo"""
        self._requirement.add_source(ContextSource.SHORT_TERM)
        return self

    def with_long_term(self, query: str = None) -> 'ContextBuilder':
        """Adiciona memória de longo prazo"""
        self._requirement.add_source(ContextSource.LONG_TERM, query)
        return self

    def with_summary(self) -> 'ContextBuilder':
        """Adiciona resumo da conversa"""
        self._requirement.add_source(ContextSource.SUMMARY)
        return self

    def with_preferences(self) -> 'ContextBuilder':
        """Adiciona preferências do usuário"""
        self._requirement.add_source(ContextSource.PREFERENCES)
        return self

    def with_web_search(
        self,
        query: str,
        max_results: int = 3,
        required: bool = False
    ) -> 'ContextBuilder':
        """Adiciona busca web"""
        self._requirement.add_tool(
            ToolType.WEB_SEARCH,
            params={'query': query, 'max_results': max_results},
            required=required
        )
        return self

    def with_file_read(
        self,
        path: str,
        required: bool = True
    ) -> 'ContextBuilder':
        """Adiciona leitura de arquivo"""
        self._requirement.add_tool(
            ToolType.FILE_READ,
            params={'path': path},
            required=required
        )
        return self

    def require_tools(self, required: bool = True) -> 'ContextBuilder':
        """Define se tools são obrigatórias"""
        self._requirement.tools_required = required
        return self

    def parallel(self, parallel: bool = True) -> 'ContextBuilder':
        """Define execução paralela de tools"""
        self._requirement.parallel_tools = parallel
        return self

    def max_tokens(self, tokens: int) -> 'ContextBuilder':
        """Define limite de tokens"""
        self._requirement.max_context_tokens = tokens
        return self

    def build(self) -> ContextRequirement:
        """Constrói o ContextRequirement"""
        return self._requirement


# Função de conveniência
def build_context() -> ContextBuilder:
    """Cria um novo ContextBuilder"""
    return ContextBuilder()
