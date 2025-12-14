"""
Base classes for LLM providers.
Defines the interface that all providers must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum


class MessageRole(str, Enum):
    """Role of a message in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in a conversation."""
    role: MessageRole
    content: str
    name: Optional[str] = None  # For tool messages
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API calls."""
        d = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


@dataclass
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost_estimate(self) -> float:
        """Rough cost estimate (varies by model)."""
        # Average pricing: $0.001 per 1K tokens
        return self.total_tokens * 0.000001


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers (OpenAI, Anthropic, Groq, etc.) must implement this interface.
    """
    
    name: str = "base"
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.default_model: Optional[str] = None
        self._configure(**kwargs)
    
    def _configure(self, **kwargs):
        """Override to add provider-specific configuration."""
        pass
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.
        
        Args:
            messages: Conversation history
            model: Model to use (or provider default)
            temperature: Creativity (0-2)
            max_tokens: Maximum response length
            tools: Available tools/functions
            **kwargs: Provider-specific options
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream a completion from the LLM.
        
        Yields:
            Content chunks as they're generated
        """
        pass
    
    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """List of models available from this provider."""
        pass
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a specific model.
        Override for provider-specific details.
        """
        return {
            "name": model,
            "provider": self.name,
            "supports_streaming": self.supports_streaming,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
        }


# Model capability ratings (1-5)
# Updated December 2024
MODEL_CAPABILITIES = {
    # OpenAI
    "gpt-4o": {"reasoning": 5, "creativity": 5, "speed": 4, "cost": 3},
    "gpt-4o-mini": {"reasoning": 4, "creativity": 4, "speed": 5, "cost": 5},
    "gpt-4-turbo": {"reasoning": 5, "creativity": 5, "speed": 3, "cost": 2},
    "gpt-3.5-turbo": {"reasoning": 3, "creativity": 3, "speed": 5, "cost": 5},
    
    # Anthropic
    "claude-3-5-sonnet-20241022": {"reasoning": 5, "creativity": 5, "speed": 4, "cost": 3},
    "claude-3-5-haiku-20241022": {"reasoning": 4, "creativity": 4, "speed": 5, "cost": 5},
    "claude-3-opus-20240229": {"reasoning": 5, "creativity": 5, "speed": 2, "cost": 1},
    
    # Groq (Free!) - Updated December 2024
    "llama-3.3-70b-versatile": {"reasoning": 5, "creativity": 4, "speed": 5, "cost": 5},  # Latest!
    "llama-3.1-8b-instant": {"reasoning": 3, "creativity": 3, "speed": 5, "cost": 5},
    "mixtral-8x7b-32768": {"reasoning": 4, "creativity": 4, "speed": 5, "cost": 5},
    "gemma2-9b-it": {"reasoning": 3, "creativity": 3, "speed": 5, "cost": 5},
    
    # Google
    "gemini-1.5-flash": {"reasoning": 4, "creativity": 4, "speed": 5, "cost": 5},
    "gemini-1.5-pro": {"reasoning": 5, "creativity": 5, "speed": 3, "cost": 3},
    
    # Mistral
    "mistral-large-latest": {"reasoning": 5, "creativity": 4, "speed": 4, "cost": 3},
    "mistral-small-latest": {"reasoning": 3, "creativity": 3, "speed": 5, "cost": 5},
    "open-mistral-7b": {"reasoning": 3, "creativity": 3, "speed": 5, "cost": 5},
}


def get_model_capabilities(model: str) -> Dict[str, int]:
    """Get capability ratings for a model."""
    return MODEL_CAPABILITIES.get(model, {
        "reasoning": 3,
        "creativity": 3, 
        "speed": 3,
        "cost": 3
    })
