"""
LLM Router - Intelligent routing to the best LLM based on task type.
Selects the optimal model considering cost, speed, and capability.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import structlog

from .base import Message, LLMResponse, LLMProvider, get_model_capabilities

logger = structlog.get_logger()


class TaskType(str, Enum):
    """
    Types of tasks that can be performed by LLMs.
    The router uses this to select the best model.
    """
    # Conversational
    CHAT = "chat"                    # General conversation
    CUSTOMER_SUPPORT = "support"     # Customer service responses
    
    # Analysis
    SUMMARIZE = "summarize"          # Summarize text/documents
    EXTRACT = "extract"              # Extract structured data
    CLASSIFY = "classify"            # Classify/categorize content
    SENTIMENT = "sentiment"          # Sentiment analysis
    
    # Generation
    WRITE = "write"                  # Creative writing
    EMAIL = "email"                  # Email drafting
    CODE = "code"                    # Code generation
    TRANSLATE = "translate"          # Translation
    
    # Reasoning
    ANALYZE = "analyze"              # Deep analysis
    PLAN = "plan"                    # Planning/strategy
    DECIDE = "decide"                # Decision making
    RESEARCH = "research"            # Research tasks
    
    # Simple
    QUICK = "quick"                  # Fast, simple responses
    FORMAT = "format"                # Formatting/restructuring


# Task type to optimal model characteristics mapping
TASK_REQUIREMENTS = {
    # Conversational - needs good speed and reasonable quality
    TaskType.CHAT: {"speed": 4, "reasoning": 3, "creativity": 3, "min_cost": 4},
    TaskType.CUSTOMER_SUPPORT: {"speed": 4, "reasoning": 3, "creativity": 2, "min_cost": 4},
    
    # Analysis - needs good reasoning
    TaskType.SUMMARIZE: {"speed": 4, "reasoning": 4, "creativity": 2, "min_cost": 4},
    TaskType.EXTRACT: {"speed": 4, "reasoning": 4, "creativity": 1, "min_cost": 4},
    TaskType.CLASSIFY: {"speed": 5, "reasoning": 3, "creativity": 1, "min_cost": 5},
    TaskType.SENTIMENT: {"speed": 5, "reasoning": 3, "creativity": 1, "min_cost": 5},
    
    # Generation - needs creativity
    TaskType.WRITE: {"speed": 3, "reasoning": 4, "creativity": 5, "min_cost": 3},
    TaskType.EMAIL: {"speed": 4, "reasoning": 3, "creativity": 3, "min_cost": 4},
    TaskType.CODE: {"speed": 3, "reasoning": 5, "creativity": 4, "min_cost": 3},
    TaskType.TRANSLATE: {"speed": 4, "reasoning": 4, "creativity": 2, "min_cost": 4},
    
    # Reasoning - needs top reasoning
    TaskType.ANALYZE: {"speed": 2, "reasoning": 5, "creativity": 4, "min_cost": 2},
    TaskType.PLAN: {"speed": 2, "reasoning": 5, "creativity": 4, "min_cost": 2},
    TaskType.DECIDE: {"speed": 3, "reasoning": 5, "creativity": 3, "min_cost": 3},
    TaskType.RESEARCH: {"speed": 2, "reasoning": 5, "creativity": 3, "min_cost": 2},
    
    # Simple - prioritize speed and cost
    TaskType.QUICK: {"speed": 5, "reasoning": 2, "creativity": 2, "min_cost": 5},
    TaskType.FORMAT: {"speed": 5, "reasoning": 2, "creativity": 1, "min_cost": 5},
}


@dataclass
class ModelSelection:
    """Result of model selection."""
    model: str
    provider: str
    score: float
    reason: str


class LLMRouter:
    """
    Intelligent LLM router that selects the best model for each task.
    
    Features:
    - Task-based routing (chat, code, analysis, etc.)
    - Cost optimization (prefers free/cheap models when appropriate)
    - Fallback chain for reliability
    - Provider health tracking
    """
    
    # Model preferences by tier (fallback chain)
    MODEL_TIERS = {
        "free": [
            ("groq", "llama-3.1-70b-versatile"),
            ("groq", "llama-3.1-8b-instant"),
            ("groq", "mixtral-8x7b-32768"),
        ],
        "cheap": [
            ("openai", "gpt-4o-mini"),
            ("anthropic", "claude-3-5-haiku-20241022"),
            ("google", "gemini-1.5-flash"),
            ("mistral", "mistral-small-latest"),
        ],
        "balanced": [
            ("anthropic", "claude-3-5-sonnet-20241022"),
            ("openai", "gpt-4o"),
            ("google", "gemini-1.5-pro"),
            ("mistral", "mistral-large-latest"),
        ],
        "premium": [
            ("anthropic", "claude-3-opus-20240229"),
            ("openai", "gpt-4-turbo"),
        ],
    }
    
    def __init__(
        self,
        providers: Dict[str, LLMProvider],
        default_tier: str = "free",
        cost_weight: float = 0.3,
        speed_weight: float = 0.3,
        quality_weight: float = 0.4,
    ):
        """
        Initialize the router.
        
        Args:
            providers: Dictionary of provider_name -> LLMProvider instances
            default_tier: Default pricing tier to use
            cost_weight: How much to weight cost in model selection
            speed_weight: How much to weight speed
            quality_weight: How much to weight quality/capability
        """
        self.providers = providers
        self.default_tier = default_tier
        self.cost_weight = cost_weight
        self.speed_weight = speed_weight
        self.quality_weight = quality_weight
        
        # Track provider health
        self._provider_failures: Dict[str, int] = {}
        self._provider_latencies: Dict[str, List[float]] = {}
    
    def _score_model(
        self,
        model: str,
        task_type: TaskType,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
    ) -> float:
        """
        Score a model for a given task type.
        Higher score = better match.
        """
        capabilities = get_model_capabilities(model)
        requirements = TASK_REQUIREMENTS.get(task_type, TASK_REQUIREMENTS[TaskType.CHAT])
        
        # Adjust weights based on preferences
        cost_w = self.cost_weight
        speed_w = self.speed_weight
        quality_w = self.quality_weight
        
        if prefer_speed:
            speed_w *= 1.5
            cost_w *= 0.7
        if prefer_quality:
            quality_w *= 1.5
            cost_w *= 0.5
        
        # Normalize weights
        total = cost_w + speed_w + quality_w
        cost_w /= total
        speed_w /= total
        quality_w /= total
        
        # Calculate score
        score = 0.0
        
        # Cost score
        if capabilities.get("cost", 3) >= requirements.get("min_cost", 3):
            score += cost_w * capabilities.get("cost", 3)
        else:
            score += cost_w * capabilities.get("cost", 3) * 0.5  # Penalty
        
        # Speed score
        if capabilities.get("speed", 3) >= requirements.get("speed", 3):
            score += speed_w * capabilities.get("speed", 3)
        else:
            score += speed_w * capabilities.get("speed", 3) * 0.5
        
        # Quality score (reasoning + creativity based on task)
        reasoning_req = requirements.get("reasoning", 3)
        creativity_req = requirements.get("creativity", 3)
        
        reasoning_score = min(capabilities.get("reasoning", 3) / max(reasoning_req, 1), 1.5)
        creativity_score = min(capabilities.get("creativity", 3) / max(creativity_req, 1), 1.5)
        
        # Weight reasoning vs creativity based on task
        if task_type in [TaskType.CODE, TaskType.ANALYZE, TaskType.PLAN, TaskType.DECIDE]:
            quality = reasoning_score * 0.7 + creativity_score * 0.3
        elif task_type in [TaskType.WRITE, TaskType.EMAIL]:
            quality = reasoning_score * 0.3 + creativity_score * 0.7
        else:
            quality = reasoning_score * 0.5 + creativity_score * 0.5
        
        score += quality_w * quality * 5  # Scale to 0-5
        
        return score
    
    def select_model(
        self,
        task_type: TaskType = TaskType.CHAT,
        tier: Optional[str] = None,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
        required_provider: Optional[str] = None,
    ) -> ModelSelection:
        """
        Select the best model for a task.
        
        Args:
            task_type: Type of task to perform
            tier: Pricing tier (free, cheap, balanced, premium)
            prefer_speed: Prioritize fast responses
            prefer_quality: Prioritize quality over cost
            required_provider: Force a specific provider
            
        Returns:
            ModelSelection with chosen model and reasoning
        """
        tier = tier or self.default_tier
        candidates = []
        
        # Get candidate models from tier and lower
        tier_order = ["free", "cheap", "balanced", "premium"]
        tier_idx = tier_order.index(tier) if tier in tier_order else 0
        
        for t in tier_order[:tier_idx + 1]:
            for provider_name, model in self.MODEL_TIERS.get(t, []):
                # Skip if provider not available or required different
                if provider_name not in self.providers:
                    continue
                if required_provider and provider_name != required_provider:
                    continue
                    
                # Skip unhealthy providers
                if self._provider_failures.get(provider_name, 0) > 3:
                    continue
                
                score = self._score_model(model, task_type, prefer_speed, prefer_quality)
                candidates.append((provider_name, model, score, t))
        
        if not candidates:
            # Fallback to first available
            for provider_name in self.providers:
                provider = self.providers[provider_name]
                if provider.available_models:
                    return ModelSelection(
                        model=provider.available_models[0],
                        provider=provider_name,
                        score=0.0,
                        reason="Fallback - no optimal model available"
                    )
            raise ValueError("No LLM providers available")
        
        # Sort by score (highest first)
        candidates.sort(key=lambda x: x[2], reverse=True)
        best = candidates[0]
        
        return ModelSelection(
            model=best[1],
            provider=best[0],
            score=best[2],
            reason=f"Best {best[3]} tier model for {task_type.value} (score: {best[2]:.2f})"
        )
    
    async def complete(
        self,
        messages: List[Message],
        task_type: TaskType = TaskType.CHAT,
        tier: Optional[str] = None,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
        **kwargs
    ) -> LLMResponse:
        """
        Complete a request using the best model for the task.
        
        Args:
            messages: Conversation messages
            task_type: Type of task
            tier: Pricing tier
            prefer_speed: Prioritize speed
            prefer_quality: Prioritize quality
            **kwargs: Additional arguments for the provider
            
        Returns:
            LLMResponse from the selected model
        """
        selection = self.select_model(
            task_type=task_type,
            tier=tier,
            prefer_speed=prefer_speed,
            prefer_quality=prefer_quality,
        )
        
        logger.info(
            "LLM routing",
            task_type=task_type.value,
            selected_model=selection.model,
            selected_provider=selection.provider,
            reason=selection.reason,
        )
        
        provider = self.providers[selection.provider]
        
        try:
            response = await provider.complete(
                messages=messages,
                model=selection.model,
                **kwargs
            )
            
            # Track successful latency
            if selection.provider not in self._provider_latencies:
                self._provider_latencies[selection.provider] = []
            self._provider_latencies[selection.provider].append(response.latency_ms)
            
            # Reset failure count on success
            self._provider_failures[selection.provider] = 0
            
            return response
            
        except Exception as e:
            # Track failure
            self._provider_failures[selection.provider] = \
                self._provider_failures.get(selection.provider, 0) + 1
            
            logger.error(
                "LLM provider failed",
                provider=selection.provider,
                model=selection.model,
                error=str(e),
                failure_count=self._provider_failures[selection.provider],
            )
            
            # Try fallback
            if self._provider_failures[selection.provider] <= 3:
                raise
            
            # Find alternative
            alt_selection = self.select_model(
                task_type=task_type,
                tier="balanced",  # Upgrade tier for fallback
                prefer_quality=True,
            )
            
            if alt_selection.provider != selection.provider:
                logger.info(
                    "Falling back to alternative provider",
                    from_provider=selection.provider,
                    to_provider=alt_selection.provider,
                )
                alt_provider = self.providers[alt_selection.provider]
                return await alt_provider.complete(
                    messages=messages,
                    model=alt_selection.model,
                    **kwargs
                )
            
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        stats = {
            "providers": {},
            "available_models": [],
        }
        
        for name, provider in self.providers.items():
            avg_latency = 0.0
            latencies = self._provider_latencies.get(name, [])
            if latencies:
                avg_latency = sum(latencies[-100:]) / len(latencies[-100:])
            
            stats["providers"][name] = {
                "available": True,
                "failure_count": self._provider_failures.get(name, 0),
                "avg_latency_ms": avg_latency,
                "models": provider.available_models,
            }
            stats["available_models"].extend(provider.available_models)
        
        return stats
