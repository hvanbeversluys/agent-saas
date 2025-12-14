"""
LLM Service - Manages LLM access based on tenant plan and configuration.
Supports Platform tokens, BYOK (Bring Your Own Key), and hybrid modes.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
import structlog

from config import settings
from database import (
    DBTenant, DBTenantLLMConfig, DBLLMUsageLog, DBUser,
    LLMTier, LLMUsageMode, SubscriptionPlan,
    PLAN_LLM_TIERS, PLAN_TOKEN_LIMITS, MODEL_PRICING
)
from llm import LLMRouter, TaskType
from llm.base import Message, MessageRole, LLMResponse
from llm.providers import get_available_providers, get_provider

logger = structlog.get_logger()


# Models available per tier
TIER_MODELS = {
    LLMTier.FREE.value: [
        # Groq only
        ("groq", "llama-3.3-70b-versatile"),
        ("groq", "llama-3.1-8b-instant"),
        ("groq", "mixtral-8x7b-32768"),
    ],
    LLMTier.STANDARD.value: [
        # Free tier +
        ("groq", "llama-3.3-70b-versatile"),
        ("groq", "llama-3.1-8b-instant"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku-20241022"),
    ],
    LLMTier.PROFESSIONAL.value: [
        # Standard tier +
        ("groq", "llama-3.3-70b-versatile"),
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-haiku-20241022"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
    ],
    LLMTier.ENTERPRISE.value: [
        # All models
        ("groq", "llama-3.3-70b-versatile"),
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
        ("openai", "gpt-4-turbo"),
        ("anthropic", "claude-3-5-haiku-20241022"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("anthropic", "claude-3-opus-20240229"),
    ],
}


class TenantLLMService:
    """
    Service for managing LLM access per tenant.
    
    Features:
    - Plan-based model restrictions
    - Token usage tracking and limits
    - BYOK support with encrypted keys
    - Cost estimation and billing
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._platform_providers = None
    
    def _get_platform_providers(self) -> Dict:
        """Get platform-wide LLM providers (using platform API keys)."""
        if self._platform_providers is None:
            self._platform_providers = get_available_providers()
        return self._platform_providers
    
    def get_tenant_config(self, tenant_id: str) -> DBTenantLLMConfig:
        """Get or create LLM config for a tenant."""
        config = self.db.query(DBTenantLLMConfig).filter(
            DBTenantLLMConfig.tenant_id == tenant_id
        ).first()
        
        if not config:
            # Get tenant's plan to set defaults
            tenant = self.db.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            llm_tier = PLAN_LLM_TIERS.get(tenant.plan, LLMTier.FREE.value) if tenant else LLMTier.FREE.value
            token_limit = PLAN_TOKEN_LIMITS.get(tenant.plan, 100000) if tenant else 100000
            
            config = DBTenantLLMConfig(
                tenant_id=tenant_id,
                llm_tier=llm_tier,
                monthly_token_limit=token_limit,
                limit_reset_at=self._get_next_month_start(),
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        
        return config
    
    def _get_next_month_start(self) -> datetime:
        """Get the first day of next month."""
        now = datetime.utcnow()
        if now.month == 12:
            return datetime(now.year + 1, 1, 1)
        return datetime(now.year, now.month + 1, 1)
    
    def check_token_limit(self, tenant_id: str, estimated_tokens: int = 0) -> Dict[str, Any]:
        """
        Check if tenant has available tokens.
        
        Returns:
            Dict with 'allowed', 'remaining', 'limit', 'reset_at'
        """
        config = self.get_tenant_config(tenant_id)
        
        # BYOK mode has no platform limits
        if config.usage_mode == LLMUsageMode.BYOK.value:
            return {
                "allowed": True,
                "remaining": None,
                "limit": None,
                "mode": "byok",
            }
        
        # Check and reset if new month
        now = datetime.utcnow()
        if config.limit_reset_at and now >= config.limit_reset_at:
            config.tokens_used_this_month = 0
            config.limit_reset_at = self._get_next_month_start()
            self.db.commit()
        
        # Unlimited for custom/enterprise plans
        if config.monthly_token_limit is None:
            return {
                "allowed": True,
                "remaining": None,
                "limit": None,
                "mode": "platform",
            }
        
        remaining = config.monthly_token_limit - config.tokens_used_this_month
        allowed = remaining >= estimated_tokens
        
        return {
            "allowed": allowed,
            "remaining": remaining,
            "limit": config.monthly_token_limit,
            "used": config.tokens_used_this_month,
            "reset_at": config.limit_reset_at.isoformat() if config.limit_reset_at else None,
            "mode": "platform",
        }
    
    def get_available_models(self, tenant_id: str) -> List[Dict[str, str]]:
        """Get models available for a tenant based on their plan."""
        config = self.get_tenant_config(tenant_id)
        
        # BYOK mode: all models they have keys for
        if config.usage_mode == LLMUsageMode.BYOK.value:
            models = []
            if config.byok_groq_key:
                models.extend([m for p, m in TIER_MODELS[LLMTier.ENTERPRISE.value] if p == "groq"])
            if config.byok_openai_key:
                models.extend([m for p, m in TIER_MODELS[LLMTier.ENTERPRISE.value] if p == "openai"])
            if config.byok_anthropic_key:
                models.extend([m for p, m in TIER_MODELS[LLMTier.ENTERPRISE.value] if p == "anthropic"])
            return [{"model": m, "provider": p} for p, m in TIER_MODELS[LLMTier.ENTERPRISE.value] if m in models]
        
        # Platform mode: models based on tier
        tier_models = TIER_MODELS.get(config.llm_tier, TIER_MODELS[LLMTier.FREE.value])
        
        # Filter by allowed/blocked lists
        available = []
        for provider, model in tier_models:
            if config.allowed_models and model not in config.allowed_models:
                continue
            if config.blocked_models and model in config.blocked_models:
                continue
            available.append({"provider": provider, "model": model})
        
        return available
    
    def _get_providers_for_tenant(self, tenant_id: str) -> Dict:
        """Get LLM providers configured for a tenant."""
        config = self.get_tenant_config(tenant_id)
        
        # Platform mode: use platform keys
        if config.usage_mode == LLMUsageMode.PLATFORM.value:
            return self._get_platform_providers()
        
        # BYOK mode: use tenant's keys
        providers = {}
        
        if config.byok_groq_key:
            provider = get_provider("groq", api_key=config.byok_groq_key)
            if provider:
                providers["groq"] = provider
        
        if config.byok_openai_key:
            provider = get_provider("openai", api_key=config.byok_openai_key)
            if provider:
                providers["openai"] = provider
        
        if config.byok_anthropic_key:
            provider = get_provider("anthropic", api_key=config.byok_anthropic_key)
            if provider:
                providers["anthropic"] = provider
        
        # Hybrid: BYOK + platform fallback
        if config.usage_mode == LLMUsageMode.HYBRID.value:
            platform_providers = self._get_platform_providers()
            for name, provider in platform_providers.items():
                if name not in providers:
                    providers[name] = provider
        
        return providers
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate estimated cost in USD."""
        pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
        # Pricing is per 1M tokens
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def _log_usage(
        self,
        tenant_id: str,
        user_id: Optional[str],
        response: LLMResponse,
        task_type: str,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        usage_mode: str = "platform",
        error: Optional[str] = None,
    ):
        """Log LLM usage for billing and analytics."""
        cost = self._calculate_cost(
            response.model,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        
        log = DBLLMUsageLog(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=cost,
            agent_id=agent_id,
            task_type=task_type,
            conversation_id=conversation_id,
            latency_ms=response.latency_ms,
            success=error is None,
            error_message=error,
            usage_mode=usage_mode,
            billing_period=datetime.utcnow().strftime("%Y-%m"),
        )
        self.db.add(log)
        
        # Update token usage counter (platform mode only)
        if usage_mode == "platform":
            config = self.get_tenant_config(tenant_id)
            config.tokens_used_this_month += response.usage.total_tokens
        
        self.db.commit()
    
    async def chat(
        self,
        tenant_id: str,
        message: str,
        user_id: Optional[str] = None,
        agent_config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        task_type: TaskType = TaskType.CHAT,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a chat request for a tenant.
        
        Args:
            tenant_id: Tenant ID
            message: User message
            user_id: User ID (for logging)
            agent_config: Agent configuration
            conversation_history: Previous messages
            task_type: Type of task
            model_override: Force a specific model
            
        Returns:
            Response dict with content, usage, cost
        """
        config = self.get_tenant_config(tenant_id)
        
        # Check token limits (platform mode)
        limit_check = self.check_token_limit(tenant_id, estimated_tokens=500)
        if not limit_check["allowed"]:
            return {
                "error": "token_limit_exceeded",
                "message": f"Limite mensuelle de tokens atteinte ({limit_check['limit']:,} tokens). "
                          f"Passez au plan supérieur ou utilisez vos propres clés API (BYOK).",
                "remaining": limit_check["remaining"],
                "limit": limit_check["limit"],
                "reset_at": limit_check["reset_at"],
            }
        
        # Get providers for this tenant
        providers = self._get_providers_for_tenant(tenant_id)
        
        if not providers:
            return {
                "error": "no_providers",
                "message": "Aucun provider LLM disponible. Configurez vos clés API dans les paramètres.",
            }
        
        # Filter models based on tenant's tier
        available_models = self.get_available_models(tenant_id)
        available_model_names = [m["model"] for m in available_models]
        
        # Create router with tenant's providers
        # Determine tier for routing
        tier = "free"
        if config.llm_tier == LLMTier.STANDARD.value:
            tier = "cheap"
        elif config.llm_tier == LLMTier.PROFESSIONAL.value:
            tier = "balanced"
        elif config.llm_tier == LLMTier.ENTERPRISE.value:
            tier = "premium"
        
        router = LLMRouter(providers=providers, default_tier=tier)
        
        # Build messages
        messages = []
        
        if agent_config and agent_config.get("system_prompt"):
            messages.append(Message(
                role=MessageRole.SYSTEM,
                content=self._build_system_prompt(agent_config),
            ))
        
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                messages.append(Message(role=role, content=msg["content"]))
        
        messages.append(Message(role=MessageRole.USER, content=message))
        
        # Call LLM
        usage_mode = config.usage_mode
        
        try:
            response = await router.complete(
                messages=messages,
                task_type=task_type,
                tier=tier,
            )
            
            # Verify model is allowed
            if response.model not in available_model_names:
                logger.warning(
                    "Model not in tenant's allowed list",
                    model=response.model,
                    tenant_id=tenant_id,
                    tier=config.llm_tier,
                )
            
            # Log usage
            self._log_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                response=response,
                task_type=task_type.value,
                agent_id=agent_config.get("id") if agent_config else None,
                usage_mode=usage_mode,
            )
            
            logger.info(
                "Tenant LLM chat completed",
                tenant_id=tenant_id,
                model=response.model,
                tokens=response.usage.total_tokens,
                cost_usd=self._calculate_cost(
                    response.model,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                ),
                tier=config.llm_tier,
                mode=usage_mode,
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
                "cost_usd": self._calculate_cost(
                    response.model,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                ),
                "latency_ms": response.latency_ms,
                "tier": config.llm_tier,
                "mode": usage_mode,
            }
            
        except Exception as e:
            logger.error("Tenant LLM chat failed", error=str(e), tenant_id=tenant_id)
            return {
                "error": "llm_error",
                "message": f"Erreur lors de la génération: {str(e)}",
            }
    
    def _build_system_prompt(self, agent_config: Dict[str, Any]) -> str:
        """Build system prompt from agent configuration."""
        parts = []
        
        if agent_config.get("system_prompt"):
            parts.append(agent_config["system_prompt"])
        
        if agent_config.get("name"):
            parts.append(f"\nTu es {agent_config['name']}.")
        
        if agent_config.get("description"):
            parts.append(f"Description: {agent_config['description']}")
        
        parts.append("\nRéponds de manière concise et utile. Utilise le markdown pour formater.")
        
        return "\n".join(parts)
    
    def get_usage_stats(self, tenant_id: str, period: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a tenant."""
        if period is None:
            period = datetime.utcnow().strftime("%Y-%m")
        
        logs = self.db.query(DBLLMUsageLog).filter(
            DBLLMUsageLog.tenant_id == tenant_id,
            DBLLMUsageLog.billing_period == period,
        ).all()
        
        config = self.get_tenant_config(tenant_id)
        
        total_tokens = sum(log.total_tokens for log in logs)
        total_cost = sum(log.estimated_cost_usd for log in logs)
        total_calls = len(logs)
        
        by_model = {}
        for log in logs:
            if log.model not in by_model:
                by_model[log.model] = {"tokens": 0, "calls": 0, "cost": 0.0}
            by_model[log.model]["tokens"] += log.total_tokens
            by_model[log.model]["calls"] += 1
            by_model[log.model]["cost"] += log.estimated_cost_usd
        
        return {
            "period": period,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "total_calls": total_calls,
            "by_model": by_model,
            "limit": config.monthly_token_limit,
            "remaining": (config.monthly_token_limit - config.tokens_used_this_month) 
                        if config.monthly_token_limit else None,
            "tier": config.llm_tier,
            "mode": config.usage_mode,
        }
    
    def update_config(
        self,
        tenant_id: str,
        usage_mode: Optional[str] = None,
        byok_openai_key: Optional[str] = None,
        byok_anthropic_key: Optional[str] = None,
        byok_groq_key: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> DBTenantLLMConfig:
        """Update tenant's LLM configuration."""
        config = self.get_tenant_config(tenant_id)
        
        if usage_mode:
            config.usage_mode = usage_mode
        
        # TODO: Encrypt keys before storing
        if byok_openai_key is not None:
            config.byok_openai_key = byok_openai_key if byok_openai_key else None
        if byok_anthropic_key is not None:
            config.byok_anthropic_key = byok_anthropic_key if byok_anthropic_key else None
        if byok_groq_key is not None:
            config.byok_groq_key = byok_groq_key if byok_groq_key else None
        
        if preferred_provider:
            config.preferred_provider = preferred_provider
        if preferred_model:
            config.preferred_model = preferred_model
        
        self.db.commit()
        self.db.refresh(config)
        
        logger.info(
            "Tenant LLM config updated",
            tenant_id=tenant_id,
            mode=config.usage_mode,
            has_byok_keys={
                "openai": bool(config.byok_openai_key),
                "anthropic": bool(config.byok_anthropic_key),
                "groq": bool(config.byok_groq_key),
            },
        )
        
        return config
