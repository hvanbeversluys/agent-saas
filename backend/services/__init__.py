"""
Agent Service - Core agent execution logic.
Combines LLM routing with agent configuration and tool execution.
"""
from typing import Optional, List, Dict, Any
import structlog

from llm import LLMRouter, TaskType
from llm.base import Message, MessageRole, LLMResponse
from llm.providers import get_available_providers
from config import settings

logger = structlog.get_logger()


class AgentService:
    """
    Service for executing agent tasks using LLMs.
    
    Features:
    - Automatic LLM selection based on task type
    - System prompt injection from agent config
    - Tool/MCP integration (planned)
    - Conversation history management
    """
    
    def __init__(self):
        self._router: Optional[LLMRouter] = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of LLM providers."""
        if self._initialized:
            return
        
        providers = get_available_providers()
        
        if providers:
            self._router = LLMRouter(
                providers=providers,
                default_tier=settings.LLM_DEFAULT_TIER,
            )
            logger.info(
                "Agent service initialized",
                providers=list(providers.keys()),
                default_tier=settings.LLM_DEFAULT_TIER,
            )
        else:
            logger.warning(
                "No LLM providers available - agent will use fallback responses"
            )
        
        self._initialized = True
    
    @property
    def is_available(self) -> bool:
        """Check if LLM service is available."""
        self._ensure_initialized()
        return self._router is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status and available models."""
        self._ensure_initialized()
        
        if not self._router:
            return {
                "available": False,
                "message": "No LLM providers configured. Add API keys in .env",
                "providers": {},
            }
        
        return {
            "available": True,
            "stats": self._router.get_stats(),
        }
    
    async def chat(
        self,
        message: str,
        agent_config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        task_type: TaskType = TaskType.CHAT,
        tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a chat request with an agent.
        
        Args:
            message: User message
            agent_config: Agent configuration (system_prompt, name, etc.)
            conversation_history: Previous messages
            task_type: Type of task for LLM routing
            tier: Override default pricing tier
            
        Returns:
            Response dict with content, model info, usage stats
        """
        self._ensure_initialized()
        
        # Build messages
        messages = []
        
        # Add system prompt from agent config
        if agent_config and agent_config.get("system_prompt"):
            system_content = self._build_system_prompt(agent_config)
            messages.append(Message(
                role=MessageRole.SYSTEM,
                content=system_content,
            ))
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                messages.append(Message(role=role, content=msg["content"]))
        
        # Add current message
        messages.append(Message(role=MessageRole.USER, content=message))
        
        # If no LLM available, return fallback
        if not self._router:
            return self._fallback_response(message, agent_config)
        
        try:
            # Call LLM through router
            response: LLMResponse = await self._router.complete(
                messages=messages,
                task_type=task_type,
                tier=tier or settings.LLM_DEFAULT_TIER,
            )
            
            logger.info(
                "Agent chat completed",
                agent=agent_config.get("name") if agent_config else "default",
                model=response.model,
                provider=response.provider,
                latency_ms=response.latency_ms,
                tokens=response.usage.total_tokens,
            )
            
            return {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "latency_ms": response.latency_ms,
            }
            
        except Exception as e:
            logger.error("Agent chat failed", error=str(e))
            return self._fallback_response(message, agent_config, str(e))
    
    def _build_system_prompt(self, agent_config: Dict[str, Any]) -> str:
        """Build system prompt from agent configuration."""
        parts = []
        
        # Base system prompt
        base_prompt = agent_config.get("system_prompt", "")
        if base_prompt:
            parts.append(base_prompt)
        
        # Agent identity
        name = agent_config.get("name")
        if name:
            parts.append(f"\nTu es {name}.")
        
        description = agent_config.get("description")
        if description:
            parts.append(f"Description: {description}")
        
        # Available tools (for context)
        tools = agent_config.get("mcp_tools", [])
        if tools:
            tool_names = [t.get("name", t) if isinstance(t, dict) else str(t) for t in tools]
            parts.append(f"\nOutils disponibles: {', '.join(tool_names)}")
        
        # Instructions
        parts.append("\nRéponds de manière concise et utile. Utilise le markdown pour formater.")
        
        return "\n".join(parts)
    
    def _fallback_response(
        self, 
        message: str, 
        agent_config: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate fallback response when LLM is unavailable."""
        agent_name = agent_config.get("name", "Assistant") if agent_config else "Assistant"
        agent_icon = agent_config.get("icon", "🤖") if agent_config else "🤖"
        
        if error:
            content = f"""⚠️ **Service temporairement indisponible**

Une erreur s'est produite: {error}

Veuillez réessayer dans quelques instants ou vérifier la configuration des providers LLM.

---
*{agent_icon} {agent_name} - Mode hors-ligne*"""
        else:
            content = f"""👋 Je suis **{agent_icon} {agent_name}**!

⚙️ **Mode démonstration** - Aucun provider LLM configuré.

Pour activer les réponses IA, ajoutez une clé API dans `.env`:
- 🆓 **Groq** (gratuit): `GROQ_API_KEY=gsk_...`
- 🆓 **Google Gemini** (gratuit): `GOOGLE_API_KEY=AIza...`
- 💳 **OpenAI**: `OPENAI_API_KEY=sk-...`

---

Votre message: *"{message[:100]}{'...' if len(message) > 100 else ''}"*"""
        
        return {
            "content": content,
            "model": "fallback",
            "provider": "none",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": 0,
            "fallback": True,
        }
    
    def detect_task_type(self, message: str) -> TaskType:
        """
        Auto-detect the task type from the user message.
        Used for optimal LLM routing.
        """
        message_lower = message.lower()
        
        # Code-related
        if any(kw in message_lower for kw in ["code", "fonction", "bug", "erreur", "python", "javascript", "api"]):
            return TaskType.CODE
        
        # Analysis
        if any(kw in message_lower for kw in ["analyse", "explique", "pourquoi", "compare"]):
            return TaskType.ANALYZE
        
        # Summarization
        if any(kw in message_lower for kw in ["résume", "résumé", "synthèse", "points clés"]):
            return TaskType.SUMMARIZE
        
        # Email
        if any(kw in message_lower for kw in ["email", "mail", "message", "répondre"]):
            return TaskType.EMAIL
        
        # Writing
        if any(kw in message_lower for kw in ["écris", "rédige", "article", "texte", "contenu"]):
            return TaskType.WRITE
        
        # Planning
        if any(kw in message_lower for kw in ["plan", "stratégie", "organise", "étapes"]):
            return TaskType.PLAN
        
        # Quick/Simple
        if len(message) < 50:
            return TaskType.QUICK
        
        return TaskType.CHAT


# Singleton instance
agent_service = AgentService()

# Export TenantLLMService
from services.llm_service import TenantLLMService

__all__ = ["AgentService", "agent_service", "TenantLLMService"]
