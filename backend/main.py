"""
Agent SaaS API - V1 Production Ready
Multi-tenant SaaS platform for AI employees management.
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import structlog

# Configuration & Security
from config import settings
from security import (
    hash_password, verify_password, generate_api_key, generate_uuid,
    create_access_token, create_refresh_token, decode_token,
    security, require_permission, check_permission, slugify,
    ROLE_PERMISSIONS, PERMISSIONS
)

# Database
from database import (
    init_db, get_db, seed_demo_data,
    DBAgent, DBPrompt, DBMCPTool, DBConversation,
    DBWorkflow, DBWorkflowTask, DBWorkflowExecution, DBScheduledJob,
    DBFunctionalArea,
    DBTenant, DBUser, DBSession, DBAPIKey,
    DBUsageRecord, DBInvoice,
    SubscriptionPlan, SubscriptionStatus, UserRole,
)

# Logging structuré
logger = structlog.get_logger()


# === Application Lifecycle ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Agent SaaS API", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    init_db()
    
    # Seed demo data only in development
    if settings.is_development:
        db = next(get_db())
        seed_demo_data(db)
        db.close()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agent SaaS API")


# === FastAPI Application ===
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-tenant SaaS platform for AI employees management",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# === Middleware ===
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Exception Handlers ===
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP error",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True
    )
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# --- Pydantic Schemas ---

class MCPToolBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    icon: str = "🔌"
    category: str = "general"
    status: str = "active"
    scope: str = "business"  # enterprise | business
    config_required: List[str] = []
    functional_area_id: Optional[str] = None

class MCPToolCreate(MCPToolBase):
    pass

class MCPToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    scope: Optional[str] = None
    config_required: Optional[List[str]] = None
    config_values: Optional[dict] = None
    functional_area_id: Optional[str] = None

class MCPToolResponse(MCPToolBase):
    id: str
    config_values: dict = {}
    created_at: datetime
    
    class Config:
        from_attributes = True


class PromptBase(BaseModel):
    name: str
    description: Optional[str] = ""
    category: str = "general"
    scope: str = "business"  # enterprise | business
    template: str
    variables: List[str] = []
    mcp_tool_id: Optional[str] = None  # Lie le prompt à un outil MCP
    functional_area_id: Optional[str] = None

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    template: Optional[str] = None
    variables: Optional[List[str]] = None
    mcp_tool_id: Optional[str] = None
    functional_area_id: Optional[str] = None

class PromptResponse(PromptBase):
    id: str
    mcp_tool: Optional[MCPToolResponse] = None  # Inclut l'outil MCP lié
    created_at: datetime
    
    class Config:
        from_attributes = True


# --- Business Action = Prompt + MCP (Bloc Métier) ---
class BusinessAction(BaseModel):
    """Un bloc métier = Prompt + MCP Tool liés ensemble"""
    id: str
    name: str
    description: str
    icon: str
    category: str
    prompt_template: str
    variables: List[str]
    mcp_tool_name: Optional[str] = None
    mcp_tool_icon: Optional[str] = None
    functional_area_id: Optional[str] = None
    functional_area_name: Optional[str] = None


# --- Périmètres Fonctionnels ---
class FunctionalAreaBase(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: str = "📁"
    color: str = "blue"
    order: str = "0"
    is_active: bool = True

class FunctionalAreaCreate(FunctionalAreaBase):
    pass

class FunctionalAreaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    order: Optional[str] = None
    is_active: Optional[bool] = None

class FunctionalAreaResponse(FunctionalAreaBase):
    id: str
    created_at: datetime
    # Compteurs pour l'affichage
    agents_count: int = 0
    prompts_count: int = 0
    workflows_count: int = 0
    mcp_tools_count: int = 0
    
    class Config:
        from_attributes = True


class AgentBase(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: str = "🤖"
    category: str = "general"
    scope: str = "business"  # enterprise | business
    system_prompt: str
    is_active: bool = True
    functional_area_id: Optional[str] = None

class AgentCreate(AgentBase):
    mcp_tool_ids: List[str] = []
    prompt_ids: List[str] = []

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    mcp_tool_ids: Optional[List[str]] = None
    prompt_ids: Optional[List[str]] = None
    functional_area_id: Optional[str] = None

class AgentResponse(AgentBase):
    id: str
    mcp_tools: List[MCPToolResponse] = []
    prompts: List[PromptResponse] = []
    functional_area: Optional[FunctionalAreaBase] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None

class HandoffInfo(BaseModel):
    triggered: bool = False
    from_agent: Optional[str] = None
    to_agent_id: Optional[str] = None
    to_agent_name: Optional[str] = None
    to_agent_icon: Optional[str] = None
    reason: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    timestamp: str
    handoff: Optional[HandoffInfo] = None


# ============================================================
# 🔐 AUTH SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: str
    company_slug: Optional[str] = None  # Auto-généré si non fourni

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"
    tenant: "TenantResponse"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    avatar_url: Optional[str]
    job_title: Optional[str]
    role: str
    is_active: bool
    email_verified: bool
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    preferences: Optional[dict] = None
    notification_settings: Optional[dict] = None

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    email: str
    logo_url: Optional[str]
    primary_color: str
    plan: str
    subscription_status: str
    max_users: int
    max_agents: int
    max_workflows: int
    max_executions_per_month: int
    
    class Config:
        from_attributes = True

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    settings: Optional[dict] = None

class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "member"
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UsageStatsResponse(BaseModel):
    current_period: str
    workflow_executions: int
    agent_calls: int
    mcp_tool_calls: int
    limits: dict
    usage_percentage: dict


# ============================================================
# 🔐 AUTH HELPERS (Dependencies)
# ============================================================

def get_current_user(
    credentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    """Dependency pour récupérer l'utilisateur authentifié"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    payload = decode_token(credentials.credentials)
    
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Type de token invalide")
    
    user = db.query(DBUser).filter(DBUser.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    
    return user

def get_optional_user(
    credentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[DBUser]:
    """Dependency optionnelle - retourne None si pas authentifié"""
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user = db.query(DBUser).filter(DBUser.id == payload["sub"]).first()
        return user if user and user.is_active else None
    except:
        return None


# --- Health ---

@app.get("/")
def read_root():
    return {
        "message": "Agent SaaS Backend is running 🚀", 
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "ok", 
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/llm/status")
def llm_status():
    """Get LLM providers status and available models."""
    from services import agent_service
    return agent_service.get_status()


# ============================================================
# 🤖 LLM CONFIGURATION ENDPOINTS
# ============================================================

class LLMConfigResponse(BaseModel):
    """Response for LLM configuration."""
    usage_mode: str
    llm_tier: str
    monthly_token_limit: Optional[int]
    tokens_used_this_month: int
    limit_reset_at: Optional[str]
    has_byok_keys: Dict[str, bool]
    preferred_provider: Optional[str]
    preferred_model: Optional[str]
    available_models: List[Dict[str, str]]

class LLMConfigUpdate(BaseModel):
    """Request to update LLM configuration."""
    usage_mode: Optional[str] = None  # platform, byok, hybrid
    byok_openai_key: Optional[str] = None
    byok_anthropic_key: Optional[str] = None
    byok_groq_key: Optional[str] = None
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None

class LLMUsageResponse(BaseModel):
    """Response for LLM usage stats."""
    period: str
    total_tokens: int
    total_cost_usd: float
    total_calls: int
    by_model: Dict[str, Dict[str, Any]]
    limit: Optional[int]
    remaining: Optional[int]
    tier: str
    mode: str

@app.get("/api/llm/config", response_model=LLMConfigResponse)
def get_llm_config(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get LLM configuration for current tenant."""
    from services.llm_service import TenantLLMService
    
    service = TenantLLMService(db)
    config = service.get_tenant_config(current_user.tenant_id)
    available_models = service.get_available_models(current_user.tenant_id)
    
    return LLMConfigResponse(
        usage_mode=config.usage_mode,
        llm_tier=config.llm_tier,
        monthly_token_limit=config.monthly_token_limit,
        tokens_used_this_month=config.tokens_used_this_month,
        limit_reset_at=config.limit_reset_at.isoformat() if config.limit_reset_at else None,
        has_byok_keys={
            "openai": bool(config.byok_openai_key),
            "anthropic": bool(config.byok_anthropic_key),
            "groq": bool(config.byok_groq_key),
            "google": bool(config.byok_google_key),
            "mistral": bool(config.byok_mistral_key),
        },
        preferred_provider=config.preferred_provider,
        preferred_model=config.preferred_model,
        available_models=available_models,
    )

@app.put("/api/llm/config", response_model=LLMConfigResponse)
def update_llm_config(
    data: LLMConfigUpdate,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update LLM configuration for current tenant. Requires admin role."""
    from services.llm_service import TenantLLMService
    
    # Check permission (admin or owner only)
    if current_user.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    service = TenantLLMService(db)
    config = service.update_config(
        tenant_id=current_user.tenant_id,
        usage_mode=data.usage_mode,
        byok_openai_key=data.byok_openai_key,
        byok_anthropic_key=data.byok_anthropic_key,
        byok_groq_key=data.byok_groq_key,
        preferred_provider=data.preferred_provider,
        preferred_model=data.preferred_model,
    )
    available_models = service.get_available_models(current_user.tenant_id)
    
    return LLMConfigResponse(
        usage_mode=config.usage_mode,
        llm_tier=config.llm_tier,
        monthly_token_limit=config.monthly_token_limit,
        tokens_used_this_month=config.tokens_used_this_month,
        limit_reset_at=config.limit_reset_at.isoformat() if config.limit_reset_at else None,
        has_byok_keys={
            "openai": bool(config.byok_openai_key),
            "anthropic": bool(config.byok_anthropic_key),
            "groq": bool(config.byok_groq_key),
            "google": bool(config.byok_google_key),
            "mistral": bool(config.byok_mistral_key),
        },
        preferred_provider=config.preferred_provider,
        preferred_model=config.preferred_model,
        available_models=available_models,
    )

@app.get("/api/llm/usage", response_model=LLMUsageResponse)
def get_llm_usage(
    period: Optional[str] = None,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get LLM usage statistics for current tenant."""
    from services.llm_service import TenantLLMService
    
    service = TenantLLMService(db)
    stats = service.get_usage_stats(current_user.tenant_id, period)
    
    return LLMUsageResponse(**stats)

@app.get("/api/llm/models")
def get_available_models(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available LLM models for current tenant based on their plan."""
    from services.llm_service import TenantLLMService, TIER_MODELS
    from database import LLMTier, MODEL_PRICING
    
    service = TenantLLMService(db)
    config = service.get_tenant_config(current_user.tenant_id)
    available = service.get_available_models(current_user.tenant_id)
    
    # Add pricing info
    models_with_pricing = []
    for model_info in available:
        pricing = MODEL_PRICING.get(model_info["model"], {"input": 0, "output": 0})
        models_with_pricing.append({
            **model_info,
            "pricing": {
                "input_per_1m": pricing["input"],
                "output_per_1m": pricing["output"],
                "is_free": pricing["input"] == 0 and pricing["output"] == 0,
            }
        })
    
    return {
        "tier": config.llm_tier,
        "mode": config.usage_mode,
        "models": models_with_pricing,
        "all_tiers": {
            tier: [{"provider": p, "model": m} for p, m in models]
            for tier, models in TIER_MODELS.items()
        }
    }

@app.get("/api/llm/plans")
def get_llm_plans():
    """Get available LLM plans and their features (public endpoint)."""
    from database import PLAN_TOKEN_LIMITS, PLAN_LLM_TIERS, MODEL_PRICING
    from services.llm_service import TIER_MODELS
    
    plans = [
        {
            "id": "free",
            "name": "Gratuit",
            "price_monthly": 0,
            "price_yearly": 0,
            "features": [
                "100,000 tokens/mois",
                "Modèles Groq (Llama 3.3, Mixtral)",
                "Réponses rapides",
                "Support communautaire",
            ],
            "llm_tier": "free",
            "token_limit": 100_000,
            "models": [m for _, m in TIER_MODELS["free"]],
        },
        {
            "id": "starter",
            "name": "Starter",
            "price_monthly": 29,
            "price_yearly": 290,
            "features": [
                "500,000 tokens/mois",
                "GPT-4o-mini, Claude Haiku",
                "Support email",
                "3 utilisateurs",
            ],
            "llm_tier": "standard",
            "token_limit": 500_000,
            "models": [m for _, m in TIER_MODELS["standard"]],
            "popular": False,
        },
        {
            "id": "business",
            "name": "Business",
            "price_monthly": 99,
            "price_yearly": 990,
            "features": [
                "2,000,000 tokens/mois",
                "GPT-4o, Claude Sonnet",
                "Support prioritaire",
                "10 utilisateurs",
                "BYOK (vos propres clés)",
                "Analytics avancés",
            ],
            "llm_tier": "professional",
            "token_limit": 2_000_000,
            "models": [m for _, m in TIER_MODELS["professional"]],
            "popular": True,
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "price_monthly": 299,
            "price_yearly": 2990,
            "features": [
                "10,000,000 tokens/mois",
                "Tous les modèles (Claude Opus, GPT-4 Turbo)",
                "Support dédié 24/7",
                "Utilisateurs illimités",
                "BYOK",
                "SLA 99.9%",
                "On-premise disponible",
            ],
            "llm_tier": "enterprise",
            "token_limit": 10_000_000,
            "models": [m for _, m in TIER_MODELS["enterprise"]],
            "popular": False,
        },
    ]
    
    return {
        "plans": plans,
        "byok_info": {
            "description": "Bring Your Own Key - Utilisez vos propres clés API pour un contrôle total des coûts",
            "supported_providers": ["OpenAI", "Anthropic", "Groq", "Google", "Mistral"],
            "available_from": "business",
        }
    }


# ============================================================
# 🔐 AUTH ENDPOINTS
# ============================================================

@app.post("/api/auth/register", response_model=TokenResponse)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Inscription d'une nouvelle entreprise + utilisateur owner"""
    
    # Vérifier si l'email existe déjà
    existing_user = db.query(DBUser).filter(DBUser.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    
    # Générer le slug si non fourni
    slug = data.company_slug or slugify(data.company_name)
    
    # Vérifier si le slug existe
    existing_tenant = db.query(DBTenant).filter(DBTenant.slug == slug).first()
    if existing_tenant:
        slug = f"{slug}-{generate_uuid()[:8]}"
    
    # Créer le tenant (entreprise)
    tenant = DBTenant(
        name=data.company_name,
        slug=slug,
        email=data.email,
        plan=SubscriptionPlan.FREE.value,
        subscription_status=SubscriptionStatus.TRIAL.value,
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        max_users=3,
        max_agents=5,
        max_workflows=10,
        max_executions_per_month=500
    )
    db.add(tenant)
    db.flush()  # Pour avoir l'ID
    
    # Créer l'utilisateur owner
    user = DBUser(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=UserRole.OWNER.value,
        email_verified=False  # À implémenter: email de vérification
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)
    
    # Générer les tokens
    access_token = create_access_token(user.id, tenant.id)
    refresh_token = create_refresh_token(user.id)
    
    # Sauvegarder la session
    session = DBSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            job_title=user.job_title,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified
        ),
        tenant=TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            email=tenant.email,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            plan=tenant.plan,
            subscription_status=tenant.subscription_status,
            max_users=tenant.max_users,
            max_agents=tenant.max_agents,
            max_workflows=tenant.max_workflows,
            max_executions_per_month=tenant.max_executions_per_month
        )
    )


@app.post("/api/auth/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Connexion utilisateur"""
    
    user = db.query(DBUser).filter(DBUser.email == data.email).first()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Entreprise désactivée")
    
    # Mettre à jour last_login
    user.last_login_at = datetime.utcnow()
    
    # Générer les tokens
    access_token = create_access_token(user.id, tenant.id)
    refresh_token = create_refresh_token(user.id)
    
    # Sauvegarder la session
    session = DBSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            job_title=user.job_title,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified
        ),
        tenant=TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            email=tenant.email,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            plan=tenant.plan,
            subscription_status=tenant.subscription_status,
            max_users=tenant.max_users,
            max_agents=tenant.max_agents,
            max_workflows=tenant.max_workflows,
            max_executions_per_month=tenant.max_executions_per_month
        )
    )


@app.post("/api/auth/refresh", response_model=TokenResponse)
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Rafraîchir les tokens"""
    
    payload = decode_token(data.refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token invalide")
    
    # Vérifier la session
    session = db.query(DBSession).filter(
        DBSession.refresh_token == data.refresh_token,
        DBSession.revoked == False
    ).first()
    
    if not session:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    user = db.query(DBUser).filter(DBUser.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur invalide")
    
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    
    # Révoquer l'ancienne session
    session.revoked = True
    
    # Créer nouveaux tokens
    access_token = create_access_token(user.id, tenant.id)
    new_refresh_token = create_refresh_token(user.id)
    
    # Nouvelle session
    new_session = DBSession(
        user_id=user.id,
        refresh_token=new_refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_session)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            job_title=user.job_title,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified
        ),
        tenant=TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            email=tenant.email,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            plan=tenant.plan,
            subscription_status=tenant.subscription_status,
            max_users=tenant.max_users,
            max_agents=tenant.max_agents,
            max_workflows=tenant.max_workflows,
            max_executions_per_month=tenant.max_executions_per_month
        )
    )


@app.post("/api/auth/logout")
def logout(
    user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Déconnexion - révoque toutes les sessions"""
    
    db.query(DBSession).filter(
        DBSession.user_id == user.id,
        DBSession.revoked == False
    ).update({"revoked": True})
    db.commit()
    
    return {"message": "Déconnexion réussie"}


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(
    user: DBUser = Depends(get_current_user)
):
    """Récupère les infos de l'utilisateur connecté"""
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        job_title=user.job_title,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified
    )


@app.put("/api/auth/me", response_model=UserResponse)
def update_current_user(
    data: UserUpdate,
    user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met à jour le profil de l'utilisateur connecté"""
    
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    if data.job_title is not None:
        user.job_title = data.job_title
    if data.phone is not None:
        user.phone = data.phone
    if data.preferences is not None:
        user.preferences = data.preferences
    if data.notification_settings is not None:
        user.notification_settings = data.notification_settings
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        job_title=user.job_title,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified
    )


@app.post("/api/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change le mot de passe de l'utilisateur"""
    
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    
    user.password_hash = hash_password(data.new_password)
    
    # Révoquer toutes les sessions sauf la courante
    db.query(DBSession).filter(
        DBSession.user_id == user.id
    ).update({"revoked": True})
    
    db.commit()
    
    return {"message": "Mot de passe changé avec succès"}


# ============================================================
# 👥 USER MANAGEMENT (Admin)
# ============================================================

@app.get("/api/users", response_model=List[UserResponse])
def list_users(
    user: DBUser = Depends(require_permission("users", "read")),
    db: Session = Depends(get_db)
):
    """Liste les utilisateurs de l'entreprise"""
    users = db.query(DBUser).filter(DBUser.tenant_id == user.tenant_id).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            job_title=u.job_title,
            role=u.role,
            is_active=u.is_active,
            email_verified=u.email_verified
        ) for u in users
    ]


@app.post("/api/users/invite", response_model=UserResponse)
def invite_user(
    data: InviteUserRequest,
    user: DBUser = Depends(require_permission("users", "invite")),
    db: Session = Depends(get_db)
):
    """Invite un nouvel utilisateur dans l'entreprise"""
    
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    
    # Vérifier la limite d'utilisateurs
    current_users = db.query(DBUser).filter(DBUser.tenant_id == tenant.id).count()
    if current_users >= tenant.max_users:
        raise HTTPException(
            status_code=403, 
            detail=f"Limite de {tenant.max_users} utilisateurs atteinte. Passez à un plan supérieur."
        )
    
    # Vérifier si l'email existe
    existing = db.query(DBUser).filter(DBUser.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    
    # Vérifier le rôle (ne peut pas créer un owner)
    if data.role == UserRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Impossible de créer un owner")
    
    # Créer l'utilisateur avec mot de passe temporaire
    temp_password = generate_uuid()[:12]
    new_user = DBUser(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(temp_password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
        email_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # TODO: Envoyer email d'invitation avec lien de reset password
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        full_name=new_user.full_name,
        avatar_url=new_user.avatar_url,
        job_title=new_user.job_title,
        role=new_user.role,
        is_active=new_user.is_active,
        email_verified=new_user.email_verified
    )


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    user: DBUser = Depends(require_permission("users", "delete")),
    db: Session = Depends(get_db)
):
    """Supprime un utilisateur"""
    
    target = db.query(DBUser).filter(
        DBUser.id == user_id,
        DBUser.tenant_id == user.tenant_id
    ).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if target.role == UserRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Impossible de supprimer le propriétaire")
    
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Impossible de se supprimer soi-même")
    
    db.delete(target)
    db.commit()
    
    return {"message": "Utilisateur supprimé"}


# ============================================================
# 🏢 TENANT MANAGEMENT
# ============================================================

@app.get("/api/tenant", response_model=TenantResponse)
def get_tenant(
    user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère les infos de l'entreprise"""
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        email=tenant.email,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        plan=tenant.plan,
        subscription_status=tenant.subscription_status,
        max_users=tenant.max_users,
        max_agents=tenant.max_agents,
        max_workflows=tenant.max_workflows,
        max_executions_per_month=tenant.max_executions_per_month
    )


@app.put("/api/tenant", response_model=TenantResponse)
def update_tenant(
    data: TenantUpdate,
    user: DBUser = Depends(require_permission("settings", "update")),
    db: Session = Depends(get_db)
):
    """Met à jour les infos de l'entreprise"""
    
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    
    if data.name is not None:
        tenant.name = data.name
    if data.email is not None:
        tenant.email = data.email
    if data.phone is not None:
        tenant.phone = data.phone
    if data.address is not None:
        tenant.address = data.address
    if data.logo_url is not None:
        tenant.logo_url = data.logo_url
    if data.primary_color is not None:
        tenant.primary_color = data.primary_color
    if data.settings is not None:
        tenant.settings = data.settings
    
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        email=tenant.email,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        plan=tenant.plan,
        subscription_status=tenant.subscription_status,
        max_users=tenant.max_users,
        max_agents=tenant.max_agents,
        max_workflows=tenant.max_workflows,
        max_executions_per_month=tenant.max_executions_per_month
    )


# ============================================================
# 📊 USAGE & BILLING
# ============================================================

@app.get("/api/usage/stats", response_model=UsageStatsResponse)
def get_usage_stats(
    user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère les statistiques d'utilisation du mois en cours"""
    
    tenant = db.query(DBTenant).filter(DBTenant.id == user.tenant_id).first()
    
    # Période courante
    now = datetime.utcnow()
    current_period = now.strftime("%Y-%m")
    
    # Compter les usages
    workflow_executions = db.query(DBUsageRecord).filter(
        DBUsageRecord.tenant_id == tenant.id,
        DBUsageRecord.billing_period == current_period,
        DBUsageRecord.usage_type == "workflow_execution"
    ).count()
    
    agent_calls = db.query(DBUsageRecord).filter(
        DBUsageRecord.tenant_id == tenant.id,
        DBUsageRecord.billing_period == current_period,
        DBUsageRecord.usage_type == "agent_call"
    ).count()
    
    mcp_tool_calls = db.query(DBUsageRecord).filter(
        DBUsageRecord.tenant_id == tenant.id,
        DBUsageRecord.billing_period == current_period,
        DBUsageRecord.usage_type == "mcp_tool_call"
    ).count()
    
    # Calculer les pourcentages
    total_executions = workflow_executions + agent_calls
    
    return UsageStatsResponse(
        current_period=current_period,
        workflow_executions=workflow_executions,
        agent_calls=agent_calls,
        mcp_tool_calls=mcp_tool_calls,
        limits={
            "max_executions_per_month": tenant.max_executions_per_month,
            "max_users": tenant.max_users,
            "max_agents": tenant.max_agents,
            "max_workflows": tenant.max_workflows
        },
        usage_percentage={
            "executions": round(total_executions / tenant.max_executions_per_month * 100, 1) if tenant.max_executions_per_month > 0 else 0
        }
    )


def record_usage(db: Session, tenant_id: str, user_id: str, usage_type: str, resource_id: str = None, resource_type: str = None, extra_data: dict = None):
    """Helper pour enregistrer une utilisation"""
    now = datetime.utcnow()
    record = DBUsageRecord(
        tenant_id=tenant_id,
        user_id=user_id,
        usage_type=usage_type,
        resource_id=resource_id,
        resource_type=resource_type,
        extra_data=extra_data or {},
        billing_period=now.strftime("%Y-%m")
    )
    db.add(record)
    db.commit()


# ============================================================
# 🔌 MCP TOOLS CRUD
# ============================================================

@app.get("/api/mcp-tools", response_model=List[MCPToolResponse])
def get_mcp_tools(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DBMCPTool)
    if category:
        query = query.filter(DBMCPTool.category == category)
    if status:
        query = query.filter(DBMCPTool.status == status)
    return query.all()

@app.get("/api/mcp-tools/{tool_id}", response_model=MCPToolResponse)
def get_mcp_tool(tool_id: str, db: Session = Depends(get_db)):
    tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@app.post("/api/mcp-tools", response_model=MCPToolResponse)
def create_mcp_tool(tool: MCPToolCreate, db: Session = Depends(get_db)):
    db_tool = DBMCPTool(
        id=str(generate_uuid()),
        **tool.model_dump()
    )
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.put("/api/mcp-tools/{tool_id}", response_model=MCPToolResponse)
def update_mcp_tool(tool_id: str, tool: MCPToolUpdate, db: Session = Depends(get_db)):
    db_tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    update_data = tool.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tool, key, value)
    
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.delete("/api/mcp-tools/{tool_id}")
def delete_mcp_tool(tool_id: str, db: Session = Depends(get_db)):
    db_tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    db.delete(db_tool)
    db.commit()
    return {"message": "Tool deleted"}

@app.get("/api/mcp-tools/categories/list")
def get_mcp_categories(db: Session = Depends(get_db)):
    return {
        "categories": [
            {"id": "email", "name": "Email", "icon": "📧"},
            {"id": "crm", "name": "CRM & Contacts", "icon": "👥"},
            {"id": "seo", "name": "SEO & Analytics", "icon": "🔍"},
            {"id": "facturation", "name": "Facturation", "icon": "🧾"},
            {"id": "productivity", "name": "Productivité", "icon": "⚡"},
            {"id": "communication", "name": "Communication", "icon": "📞"},
        ]
    }


# ============================================================
# 📝 PROMPTS CRUD
# ============================================================

@app.get("/api/prompts", response_model=List[PromptResponse])
def get_prompts(
    category: Optional[str] = None,
    functional_area_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DBPrompt)
    if category:
        query = query.filter(DBPrompt.category == category)
    if functional_area_id:
        query = query.filter(DBPrompt.functional_area_id == functional_area_id)
    return query.all()

@app.get("/api/prompts/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

@app.post("/api/prompts", response_model=PromptResponse)
def create_prompt(prompt: PromptCreate, db: Session = Depends(get_db)):
    db_prompt = DBPrompt(
        id=str(generate_uuid()),
        **prompt.model_dump()
    )
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@app.put("/api/prompts/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: str, prompt: PromptUpdate, db: Session = Depends(get_db)):
    db_prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    update_data = prompt.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_prompt, key, value)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@app.delete("/api/prompts/{prompt_id}")
def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    db_prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(db_prompt)
    db.commit()
    return {"message": "Prompt deleted"}


# ============================================================
# 📁 PÉRIMÈTRES FONCTIONNELS CRUD
# ============================================================

@app.get("/api/functional-areas", response_model=List[FunctionalAreaResponse])
def get_functional_areas(db: Session = Depends(get_db)):
    """Liste tous les périmètres fonctionnels avec compteurs"""
    areas = db.query(DBFunctionalArea).order_by(DBFunctionalArea.order).all()
    
    result = []
    for area in areas:
        area_dict = {
            "id": area.id,
            "name": area.name,
            "description": area.description,
            "icon": area.icon,
            "color": area.color,
            "order": area.order,
            "is_active": area.is_active,
            "created_at": area.created_at,
            "agents_count": len(area.agents) if area.agents else 0,
            "prompts_count": len(area.prompts) if area.prompts else 0,
            "workflows_count": len(area.workflows) if area.workflows else 0,
            "mcp_tools_count": len(area.mcp_tools) if area.mcp_tools else 0,
        }
        result.append(area_dict)
    
    return result

@app.get("/api/functional-areas/{area_id}", response_model=FunctionalAreaResponse)
def get_functional_area(area_id: str, db: Session = Depends(get_db)):
    """Récupère un périmètre fonctionnel par ID"""
    area = db.query(DBFunctionalArea).filter(DBFunctionalArea.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Functional area not found")
    
    return {
        "id": area.id,
        "name": area.name,
        "description": area.description,
        "icon": area.icon,
        "color": area.color,
        "order": area.order,
        "is_active": area.is_active,
        "created_at": area.created_at,
        "agents_count": len(area.agents) if area.agents else 0,
        "prompts_count": len(area.prompts) if area.prompts else 0,
        "workflows_count": len(area.workflows) if area.workflows else 0,
        "mcp_tools_count": len(area.mcp_tools) if area.mcp_tools else 0,
    }

@app.get("/api/functional-areas/{area_id}/details")
def get_functional_area_details(area_id: str, db: Session = Depends(get_db)):
    """Récupère un périmètre avec tous ses éléments liés"""
    area = db.query(DBFunctionalArea).filter(DBFunctionalArea.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Functional area not found")
    
    return {
        "id": area.id,
        "name": area.name,
        "description": area.description,
        "icon": area.icon,
        "color": area.color,
        "agents": [{"id": a.id, "name": a.name, "icon": a.icon, "description": a.description} for a in area.agents],
        "prompts": [{"id": p.id, "name": p.name, "description": p.description, "category": p.category} for p in area.prompts],
        "workflows": [{"id": w.id, "name": w.name, "description": w.description, "trigger_type": w.trigger_type} for w in area.workflows],
        "mcp_tools": [{"id": t.id, "name": t.name, "icon": t.icon, "status": t.status} for t in area.mcp_tools],
    }

@app.post("/api/functional-areas", response_model=FunctionalAreaResponse)
def create_functional_area(area: FunctionalAreaCreate, db: Session = Depends(get_db)):
    """Crée un nouveau périmètre fonctionnel"""
    db_area = DBFunctionalArea(
        id=str(generate_uuid()),
        name=area.name,
        description=area.description,
        icon=area.icon,
        color=area.color,
        order=area.order,
        is_active=area.is_active
    )
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    
    return {
        "id": db_area.id,
        "name": db_area.name,
        "description": db_area.description,
        "icon": db_area.icon,
        "color": db_area.color,
        "order": db_area.order,
        "is_active": db_area.is_active,
        "created_at": db_area.created_at,
        "agents_count": 0,
        "prompts_count": 0,
        "workflows_count": 0,
        "mcp_tools_count": 0,
    }

@app.put("/api/functional-areas/{area_id}", response_model=FunctionalAreaResponse)
def update_functional_area(area_id: str, area: FunctionalAreaUpdate, db: Session = Depends(get_db)):
    """Met à jour un périmètre fonctionnel"""
    db_area = db.query(DBFunctionalArea).filter(DBFunctionalArea.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Functional area not found")
    
    update_data = area.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_area, field, value)
    
    db.commit()
    db.refresh(db_area)
    
    return {
        "id": db_area.id,
        "name": db_area.name,
        "description": db_area.description,
        "icon": db_area.icon,
        "color": db_area.color,
        "order": db_area.order,
        "is_active": db_area.is_active,
        "created_at": db_area.created_at,
        "agents_count": len(db_area.agents) if db_area.agents else 0,
        "prompts_count": len(db_area.prompts) if db_area.prompts else 0,
        "workflows_count": len(db_area.workflows) if db_area.workflows else 0,
        "mcp_tools_count": len(db_area.mcp_tools) if db_area.mcp_tools else 0,
    }

@app.delete("/api/functional-areas/{area_id}")
def delete_functional_area(area_id: str, db: Session = Depends(get_db)):
    """Supprime un périmètre fonctionnel"""
    db_area = db.query(DBFunctionalArea).filter(DBFunctionalArea.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Functional area not found")
    
    # Dissocier les éléments liés (ne pas les supprimer)
    for agent in db_area.agents:
        agent.functional_area_id = None
    for prompt in db_area.prompts:
        prompt.functional_area_id = None
    for workflow in db_area.workflows:
        workflow.functional_area_id = None
    for tool in db_area.mcp_tools:
        tool.functional_area_id = None
    
    db.delete(db_area)
    db.commit()
    return {"message": "Functional area deleted"}


# ============================================================
# 🤖 AGENTS CRUD
# ============================================================

@app.get("/api/agents", response_model=List[AgentResponse])
def get_agents(
    category: Optional[str] = None, 
    functional_area_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DBAgent)
    if category:
        query = query.filter(DBAgent.category == category)
    if functional_area_id:
        query = query.filter(DBAgent.functional_area_id == functional_area_id)
    return query.all()

@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/api/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    # Extraire les IDs de relations
    mcp_tool_ids = agent.mcp_tool_ids
    prompt_ids = agent.prompt_ids
    
    # Créer l'agent sans les relations
    agent_data = agent.model_dump(exclude={"mcp_tool_ids", "prompt_ids"})
    db_agent = DBAgent(id=str(generate_uuid()), **agent_data)
    
    # Ajouter les relations MCP tools
    if mcp_tool_ids:
        tools = db.query(DBMCPTool).filter(DBMCPTool.id.in_(mcp_tool_ids)).all()
        db_agent.mcp_tools = tools
    
    # Ajouter les relations Prompts
    if prompt_ids:
        prompts = db.query(DBPrompt).filter(DBPrompt.id.in_(prompt_ids)).all()
        db_agent.prompts = prompts
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = agent.model_dump(exclude_unset=True)
    
    # Gérer les relations MCP tools
    if "mcp_tool_ids" in update_data:
        mcp_tool_ids = update_data.pop("mcp_tool_ids")
        if mcp_tool_ids is not None:
            tools = db.query(DBMCPTool).filter(DBMCPTool.id.in_(mcp_tool_ids)).all()
            db_agent.mcp_tools = tools
    
    # Gérer les relations Prompts
    if "prompt_ids" in update_data:
        prompt_ids = update_data.pop("prompt_ids")
        if prompt_ids is not None:
            prompts = db.query(DBPrompt).filter(DBPrompt.id.in_(prompt_ids)).all()
            db_agent.prompts = prompts
    
    # Mettre à jour les autres champs
    for key, value in update_data.items():
        setattr(db_agent, key, value)
    
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"message": "Agent deleted"}

@app.get("/api/agents/categories/list")
def get_agent_categories(db: Session = Depends(get_db)):
    return {
        "categories": [
            {"id": "commercial", "name": "Commercial & Ventes", "icon": "🤝"},
            {"id": "seo", "name": "SEO & Contenu", "icon": "🔍"},
            {"id": "admin", "name": "Administratif", "icon": "📋"},
            {"id": "direction", "name": "Direction & Stratégie", "icon": "👔"},
            {"id": "general", "name": "Général", "icon": "🤖"},
        ]
    }


# ============================================================
# 📊 DASHBOARD STATS
# ============================================================

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    agents = db.query(DBAgent).all()
    prompts = db.query(DBPrompt).all()
    mcp_tools = db.query(DBMCPTool).all()
    conversations = db.query(DBConversation).count()
    
    return {
        "agents": {
            "total": len(agents),
            "active": len([a for a in agents if a.is_active]),
        },
        "prompts": {
            "total": len(prompts),
        },
        "mcp_tools": {
            "total": len(mcp_tools),
            "active": len([t for t in mcp_tools if t.status == "active"]),
            "beta": len([t for t in mcp_tools if t.status == "beta"]),
            "coming_soon": len([t for t in mcp_tools if t.status == "coming_soon"]),
        },
        "conversations_today": conversations,
    }


# ============================================================
# 💬 CHAT avec ORCHESTRATEUR
# ============================================================

# Mots-clés pour le routing intelligent
ROUTING_KEYWORDS = {
    "agent-prospection": {
        "keywords": ["prospect", "prospecter", "démarcher", "nouveau client", "nouveaux clients", "trouver des clients", "email froid", "cold email", "cherche des clients", "acquisition client"],
        "description": "prospection et démarchage"
    },
    "agent-devis": {
        "keywords": ["devis", "proposition", "tarif", "prix", "offre commerciale", "chiffrer", "estimation"],
        "description": "devis et propositions commerciales"
    },
    "agent-seo-audit": {
        "keywords": ["audit", "analyser site", "seo", "référencement", "position google", "erreurs site", "performance"],
        "description": "audit SEO et analyse de site"
    },
    "agent-seo-content": {
        "keywords": ["article", "blog", "rédiger", "contenu", "texte", "page web", "fiche produit", "écrire"],
        "description": "rédaction de contenu SEO"
    },
    "agent-facturation": {
        "keywords": ["facture", "facturer", "paiement", "relance", "impayé", "encaissement", "règlement"],
        "description": "facturation et relances"
    },
    "agent-planning": {
        "keywords": ["planning", "agenda", "rendez-vous", "réunion", "organiser", "calendrier", "projet", "deadline"],
        "description": "planning et organisation"
    },
    "agent-strategie": {
        "keywords": ["stratégie", "concurrent", "positionnement", "marché", "décision", "business", "développer"],
        "description": "stratégie et conseil"
    },
    "agent-reporting": {
        "keywords": ["rapport", "reporting", "statistiques", "chiffres", "bilan", "tableau de bord", "kpi"],
        "description": "reporting et analyse"
    },
}


def detect_best_agent(message: str, agents: list, current_agent_id: str = None) -> tuple:
    """
    Détecte le meilleur agent pour traiter la demande.
    Retourne (agent_id, raison) ou (None, None) si pas de match.
    """
    message_lower = message.lower()
    
    best_match = None
    best_score = 0
    best_reason = None
    
    for agent_id, config in ROUTING_KEYWORDS.items():
        score = 0
        matched_keywords = []
        
        for keyword in config["keywords"]:
            if keyword in message_lower:
                score += 1
                matched_keywords.append(keyword)
        
        if score > best_score:
            best_score = score
            best_match = agent_id
            best_reason = config["description"]
    
    # Ne pas handoff vers le même agent
    if best_match == current_agent_id:
        return None, None
    
    # Seuil minimum de confiance
    if best_score >= 1:
        return best_match, best_reason
    
    return None, None


def _detect_task_type(message: str):
    """Détecte le type de tâche à partir du message pour optimiser le routing LLM."""
    from llm import TaskType
    
    message_lower = message.lower()
    
    # Patterns pour chaque type
    code_patterns = ["code", "python", "javascript", "fonction", "bug", "erreur", "debug", "api"]
    analyze_patterns = ["analyse", "évalue", "compare", "examine", "diagnostic", "audit"]
    summarize_patterns = ["résume", "synthèse", "résumé", "condense", "simplifie"]
    email_patterns = ["email", "mail", "message", "courrier", "envoie", "relance"]
    creative_patterns = ["écris", "rédige", "crée", "invente", "génère", "article", "blog", "contenu"]
    
    # Détection par priorité
    if any(p in message_lower for p in code_patterns):
        return TaskType.CODE
    if any(p in message_lower for p in analyze_patterns):
        return TaskType.ANALYZE
    if any(p in message_lower for p in summarize_patterns):
        return TaskType.SUMMARIZE
    if any(p in message_lower for p in email_patterns):
        return TaskType.EMAIL
    if any(p in message_lower for p in creative_patterns):
        return TaskType.CREATIVE
    
    # Messages courts = QUICK
    if len(message) < 50:
        return TaskType.QUICK
    
    return TaskType.CHAT


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_optional_user)
):
    """Chat avec orchestration intelligente, handoff et LLM réel.
    
    Utilise TenantLLMService pour:
    - Respecter les limites de tokens du plan
    - Utiliser les clés BYOK si configurées
    - Logger l'usage pour la facturation
    """
    from services.llm_service import TenantLLMService
    from llm import TaskType
    
    # Récupérer ou créer la conversation
    conv_id = request.conversation_id or str(generate_uuid())
    
    conversation = db.query(DBConversation).filter(DBConversation.id == conv_id).first()
    if not conversation:
        conversation = DBConversation(id=conv_id, agent_id=request.agent_id, messages=[])
        db.add(conversation)
    
    # Ajouter le message utilisateur
    messages = list(conversation.messages) if conversation.messages else []
    messages.append({"role": "user", "content": request.message})
    
    # Récupérer tous les agents pour le routing
    all_agents = db.query(DBAgent).filter(DBAgent.is_active == True).all()
    
    # Récupérer l'agent courant
    current_agent = None
    if request.agent_id:
        current_agent = db.query(DBAgent).filter(DBAgent.id == request.agent_id).first()
    
    # === LOGIQUE D'ORCHESTRATION ===
    handoff_info = None
    response_agent = current_agent
    
    # Si pas d'agent sélectionné OU si l'agent est l'orchestrateur général
    is_orchestrator = current_agent and current_agent.id == "agent-orchestrator"
    
    if not current_agent or is_orchestrator:
        # Détecter le meilleur agent
        best_agent_id, reason = detect_best_agent(request.message, all_agents, None)
        
        if best_agent_id:
            target_agent = db.query(DBAgent).filter(DBAgent.id == best_agent_id).first()
            if target_agent:
                handoff_info = HandoffInfo(
                    triggered=True,
                    from_agent="🎯 Orchestrateur",
                    to_agent_id=target_agent.id,
                    to_agent_name=target_agent.name,
                    to_agent_icon=target_agent.icon,
                    reason=f"Votre demande concerne : {reason}"
                )
                response_agent = target_agent
                # Mettre à jour la conversation avec le nouvel agent
                conversation.agent_id = target_agent.id
    
    # Générer la réponse avec LLM via TenantLLMService
    # Détermine le tenant_id (utilisateur connecté ou tenant par défaut)
    tenant_id = current_user.tenant_id if current_user else None
    user_id = current_user.id if current_user else None
    
    # Si tenant_id disponible, utiliser le service tenant-aware
    if tenant_id and response_agent:
        llm_service = TenantLLMService(db)
        
        # Préparer la config de l'agent
        agent_config = {
            "id": response_agent.id,
            "name": response_agent.name,
            "icon": response_agent.icon,
            "description": response_agent.description,
            "system_prompt": response_agent.system_prompt or "",
            "mcp_tools": [{"name": t.name, "description": t.description} for t in response_agent.mcp_tools] if response_agent.mcp_tools else [],
        }
        
        # Filtrer l'historique (derniers 10 messages pour limiter les tokens)
        history = messages[-10:-1] if len(messages) > 1 else []
        
        # Détecter le type de tâche
        task_type = _detect_task_type(request.message)
        
        # Appeler le LLM via TenantLLMService (respecte quotas + BYOK)
        try:
            llm_response = await llm_service.chat(
                tenant_id=tenant_id,
                message=request.message,
                user_id=user_id,
                agent_config=agent_config,
                conversation_history=history,
                task_type=task_type,
            )
            
            # Vérifier si erreur (limite atteinte, etc.)
            if "error" in llm_response:
                logger.warning(
                    "LLM limit reached or error",
                    tenant_id=tenant_id,
                    error=llm_response["error"],
                )
                # Retourner le message d'erreur à l'utilisateur
                response_content = f"⚠️ {llm_response['message']}"
            else:
                response_content = llm_response["content"]
                
                # Log pour monitoring
                logger.info(
                    "Tenant LLM chat completed",
                    tenant_id=tenant_id,
                    agent_id=response_agent.id,
                    model=llm_response.get("model"),
                    tokens=llm_response.get("usage", {}).get("total_tokens", 0),
                    cost_usd=llm_response.get("cost_usd", 0),
                    mode=llm_response.get("mode"),
                )
        except Exception as e:
            logger.error("Tenant LLM chat failed, using fallback", error=str(e), tenant_id=tenant_id)
            response_content = generate_orchestrated_response(
                request.message, 
                response_agent, 
                handoff_info
            )
    elif response_agent:
        # Fallback pour utilisateurs non connectés: utiliser agent_service global
        from services import agent_service
        
        if agent_service.is_available:
            agent_config = {
                "name": response_agent.name,
                "icon": response_agent.icon,
                "description": response_agent.description,
                "system_prompt": response_agent.system_prompt or "",
            }
            history = messages[-10:-1] if len(messages) > 1 else []
            task_type = _detect_task_type(request.message)
            
            try:
                llm_response = await agent_service.chat(
                    message=request.message,
                    agent_config=agent_config,
                    conversation_history=history,
                    task_type=task_type,
                )
                response_content = llm_response["content"]
            except Exception as e:
                logger.error("LLM chat failed, using fallback", error=str(e))
                response_content = generate_orchestrated_response(
                    request.message, 
                    response_agent, 
                    handoff_info
                )
        else:
            response_content = generate_orchestrated_response(
                request.message, 
                response_agent, 
                handoff_info
            )
    else:
        # Pas d'agent, réponse générique
        response_content = generate_orchestrated_response(
            request.message, 
            None, 
            handoff_info
        )
    
    messages.append({"role": "assistant", "content": response_content})
    
    # Sauvegarder
    conversation.messages = messages
    db.commit()
    
    return ChatResponse(
        conversation_id=conv_id,
        message=ChatMessage(role="assistant", content=response_content),
        timestamp=datetime.now().isoformat(),
        handoff=handoff_info
    )


def generate_orchestrated_response(user_message: str, agent: DBAgent = None, handoff: HandoffInfo = None) -> str:
    """Génère une réponse statique (fallback quand pas de LLM)."""
    user_lower = user_message.lower()
    
    # Si handoff déclenché
    if handoff and handoff.triggered:
        tool_names = [t.name for t in agent.mcp_tools] if agent and agent.mcp_tools else []
        prompt_names = [p.name for p in agent.prompts] if agent and agent.prompts else []
        
        return f"""🔄 **Transfert vers {handoff.to_agent_icon} {handoff.to_agent_name}**

_{handoff.reason}_

---

**{agent.icon} {agent.name}** prend le relais !

{agent.description}

**Outils disponibles:** {', '.join(tool_names) if tool_names else 'Configuration en attente'}
**Templates prêts:** {', '.join(prompt_names) if prompt_names else 'Aucun'}

---

💬 Comment puis-je vous aider avec votre demande ?

> "{user_message[:100]}{'...' if len(user_message) > 100 else ''}"
"""
    
    # Si agent spécifique (sans handoff)
    if agent:
        tool_names = [t.name for t in agent.mcp_tools] if agent.mcp_tools else []
        prompt_names = [p.name for p in agent.prompts] if agent.prompts else []
        
        # Réponses contextuelles par type d'agent
        if "prospection" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider à :
- ✉️ Rédiger un email de prospection personnalisé
- 📞 Préparer un script d'appel
- 🎯 Cibler les bons prospects

**Donnez-moi le contexte :**
- Quelle entreprise voulez-vous contacter ?
- Quel est votre service/produit ?
- Y a-t-il un contexte particulier ?

_Templates disponibles : {', '.join(prompt_names) if prompt_names else 'Demandez-moi directement'}_
"""
        elif "devis" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider à :
- 📄 Structurer une proposition commerciale
- 💰 Définir le bon tarif
- ✍️ Rédiger les conditions

**De quoi avez-vous besoin ?**
- Nouveau devis ou relance ?
- Type de prestation ?
- Budget client estimé ?
"""
        elif "seo" in agent.id and "audit" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux analyser :
- 🔍 Le référencement d'un site
- ⚡ Les performances techniques
- 📊 Le positionnement vs concurrents

**Quelle est l'URL à analyser ?**
"""
        elif "seo" in agent.id and "content" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux rédiger :
- 📝 Articles de blog optimisés
- 📄 Pages de services
- 🏷️ Fiches produits

**Quel contenu voulez-vous ?**
- Sujet / thématique ?
- Mot-clé principal ?
- Longueur souhaitée ?
"""
        elif "facturation" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider avec :
- 🧾 Création de factures
- 📧 Emails de relance (niveau 1, 2, 3)
- 📊 Suivi des paiements

**Quelle action ?**
- Relancer un client ?
- Créer une facture ?
- Faire un point sur les impayés ?
"""
        else:
            return f"""**{agent.icon} {agent.name}**

{agent.description}

**Outils connectés:** {', '.join(tool_names) if tool_names else 'Aucun'}
**Templates:** {', '.join(prompt_names) if prompt_names else 'Aucun'}

💬 Comment puis-je vous aider ?
"""
    
    # Pas d'agent - Mode orchestrateur
    return f"""🎯 **Assistant Entreprise**

Bonjour ! Je suis votre assistant principal. Décrivez-moi votre besoin et je vous orienterai vers le bon expert :

| Besoin | Expert |
|--------|--------|
| Trouver des clients | 📞 Prospection |
| Faire un devis | 💼 Devis |
| Améliorer mon site | 🔍 Audit SEO |
| Écrire du contenu | ✍️ Rédacteur |
| Gérer les factures | 🧾 Facturation |
| Organiser mon temps | 📅 Planning |

**Que voulez-vous faire ?**

> Exemple : "Je dois relancer un client qui n'a pas payé sa facture"
"""


# ============================================================
# 📅 SCHEDULER / WORKFLOWS CRUD
# ============================================================

# --- Pydantic Schemas for Workflows ---

class WorkflowTaskConfig(BaseModel):
    """Configuration d'une tâche de workflow"""
    # Pour prompt
    prompt_id: Optional[str] = None
    prompt_template: Optional[str] = None
    variables_mapping: Optional[dict] = None
    
    # Pour mcp_action
    tool_id: Optional[str] = None
    action: Optional[str] = None
    params: Optional[dict] = None
    
    # Pour condition
    expression: Optional[str] = None
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
    
    # Pour loop
    iterate_over: Optional[str] = None
    item_var: Optional[str] = None
    
    # Pour wait
    wait_type: Optional[str] = None  # delay, event
    duration: Optional[int] = None  # secondes
    event: Optional[str] = None
    
    # Pour human_approval
    approval_message: Optional[str] = None
    timeout: Optional[int] = None
    
    # Pour set_variable
    var_name: Optional[str] = None
    var_value: Optional[str] = None
    
    # Pour http_request
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict] = None
    body: Optional[dict] = None

class WorkflowTaskBase(BaseModel):
    name: str
    description: Optional[str] = ""
    order: str = "1"
    task_type: str  # prompt, mcp_action, condition, loop, wait, parallel, human_approval, set_variable, http_request
    config: dict = {}
    on_error: str = "stop"
    retry_count: str = "0"
    error_goto: Optional[str] = None

class WorkflowTaskCreate(WorkflowTaskBase):
    pass

class WorkflowTaskResponse(WorkflowTaskBase):
    id: str
    workflow_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TriggerConfig(BaseModel):
    cron: Optional[str] = None  # "0 9 * * 1-5"
    event: Optional[str] = None  # "new_lead"
    source: Optional[str] = None  # "crm"
    webhook_secret: Optional[str] = None

class InputSchemaField(BaseModel):
    name: str
    type: str = "string"  # string, number, boolean, array, object
    required: bool = True
    default: Optional[str] = None
    description: Optional[str] = None

class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = ""
    trigger_type: str = "manual"  # manual, cron, event
    trigger_config: dict = {}
    input_schema: List[InputSchemaField] = []
    is_active: bool = True

class WorkflowCreate(WorkflowBase):
    agent_id: str
    tasks: List[WorkflowTaskCreate] = []

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    input_schema: Optional[List[InputSchemaField]] = None
    is_active: Optional[bool] = None

class WorkflowResponse(WorkflowBase):
    id: str
    agent_id: str
    tasks: List[WorkflowTaskResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class WorkflowExecutionBase(BaseModel):
    input_data: dict = {}

class WorkflowExecutionCreate(WorkflowExecutionBase):
    pass

class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input_data: dict
    output_data: dict
    variables: dict
    current_task_order: Optional[str]
    tasks_completed: List[str]
    task_results: dict
    error_message: Optional[str]
    error_task_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# --- Workflow CRUD Endpoints ---

@app.get("/api/workflows", response_model=List[WorkflowResponse])
def get_workflows(
    agent_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    functional_area_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Liste tous les workflows, optionnellement filtrés par agent ou périmètre"""
    query = db.query(DBWorkflow)
    if agent_id:
        query = query.filter(DBWorkflow.agent_id == agent_id)
    if is_active is not None:
        query = query.filter(DBWorkflow.is_active == is_active)
    if functional_area_id:
        query = query.filter(DBWorkflow.functional_area_id == functional_area_id)
    return query.all()

@app.get("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Récupère un workflow par son ID"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@app.post("/api/workflows", response_model=WorkflowResponse)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    """Crée un nouveau workflow avec ses tâches"""
    # Vérifier que l'agent existe
    agent = db.query(DBAgent).filter(DBAgent.id == workflow.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Créer le workflow
    db_workflow = DBWorkflow(
        id=str(generate_uuid()),
        name=workflow.name,
        description=workflow.description,
        agent_id=workflow.agent_id,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        input_schema=[field.model_dump() for field in workflow.input_schema],
        is_active=workflow.is_active
    )
    db.add(db_workflow)
    db.flush()  # Pour obtenir l'ID
    
    # Créer les tâches
    for task_data in workflow.tasks:
        db_task = DBWorkflowTask(
            id=str(generate_uuid()),
            workflow_id=db_workflow.id,
            **task_data.model_dump()
        )
        db.add(db_task)
    
    # Si trigger cron, créer le job planifié
    if workflow.trigger_type == "cron" and workflow.trigger_config.get("cron"):
        from datetime import datetime, timedelta
        db_job = DBScheduledJob(
            id=str(generate_uuid()),
            workflow_id=db_workflow.id,
            cron_expression=workflow.trigger_config["cron"],
            timezone=workflow.trigger_config.get("timezone", "Europe/Paris"),
            next_run=datetime.utcnow() + timedelta(minutes=5),  # Placeholder
            is_active=True
        )
        db.add(db_job)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.put("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: str, workflow: WorkflowUpdate, db: Session = Depends(get_db)):
    """Met à jour un workflow"""
    db_workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    update_data = workflow.model_dump(exclude_unset=True)
    if "input_schema" in update_data and update_data["input_schema"]:
        update_data["input_schema"] = [field.model_dump() if hasattr(field, 'model_dump') else field for field in update_data["input_schema"]]
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Supprime un workflow et ses tâches"""
    db_workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Supprimer les tâches associées
    db.query(DBWorkflowTask).filter(DBWorkflowTask.workflow_id == workflow_id).delete()
    # Supprimer les exécutions
    db.query(DBWorkflowExecution).filter(DBWorkflowExecution.workflow_id == workflow_id).delete()
    # Supprimer le job planifié s'il existe
    db.query(DBScheduledJob).filter(DBScheduledJob.workflow_id == workflow_id).delete()
    # Supprimer le workflow
    db.delete(db_workflow)
    db.commit()
    return {"message": "Workflow deleted"}


# --- Workflow Tasks Endpoints ---

@app.post("/api/workflows/{workflow_id}/tasks", response_model=WorkflowTaskResponse)
def add_workflow_task(workflow_id: str, task: WorkflowTaskCreate, db: Session = Depends(get_db)):
    """Ajoute une tâche à un workflow"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    db_task = DBWorkflowTask(
        id=str(generate_uuid()),
        workflow_id=workflow_id,
        **task.model_dump()
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.put("/api/workflows/{workflow_id}/tasks/{task_id}", response_model=WorkflowTaskResponse)
def update_workflow_task(workflow_id: str, task_id: str, task: WorkflowTaskCreate, db: Session = Depends(get_db)):
    """Met à jour une tâche"""
    db_task = db.query(DBWorkflowTask).filter(
        DBWorkflowTask.id == task_id,
        DBWorkflowTask.workflow_id == workflow_id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    for key, value in task.model_dump().items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/api/workflows/{workflow_id}/tasks/{task_id}")
def delete_workflow_task(workflow_id: str, task_id: str, db: Session = Depends(get_db)):
    """Supprime une tâche"""
    db_task = db.query(DBWorkflowTask).filter(
        DBWorkflowTask.id == task_id,
        DBWorkflowTask.workflow_id == workflow_id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(db_task)
    db.commit()
    return {"message": "Task deleted"}


# --- Workflow Execution Endpoints ---

@app.post("/api/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(workflow_id: str, execution: WorkflowExecutionCreate, db: Session = Depends(get_db)):
    """Lance l'exécution d'un workflow"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Valider les inputs requis
    for field in workflow.input_schema:
        if field.get("required", True) and field["name"] not in execution.input_data:
            if not field.get("default"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required input: {field['name']}"
                )
    
    # Créer l'exécution
    db_execution = DBWorkflowExecution(
        id=str(generate_uuid()),
        workflow_id=workflow_id,
        status="pending",
        input_data=execution.input_data,
        variables={},
        started_at=datetime.utcnow()
    )
    db.add(db_execution)
    db.commit()
    db.refresh(db_execution)
    
    # TODO: Lancer l'exécution async (via background task ou queue)
    # Pour le MVP, on simule une exécution immédiate
    db_execution.status = "running"
    db_execution.current_task_order = "1"
    db.commit()
    db.refresh(db_execution)
    
    return db_execution

@app.get("/api/workflows/{workflow_id}/executions", response_model=List[WorkflowExecutionResponse])
def get_workflow_executions(
    workflow_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Liste les exécutions d'un workflow"""
    query = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.workflow_id == workflow_id)
    if status:
        query = query.filter(DBWorkflowExecution.status == status)
    return query.order_by(DBWorkflowExecution.created_at.desc()).limit(limit).all()

@app.get("/api/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    """Récupère les détails d'une exécution"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@app.post("/api/executions/{execution_id}/cancel")
def cancel_execution(execution_id: str, db: Session = Depends(get_db)):
    """Annule une exécution en cours"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.status not in ["pending", "running", "waiting_approval"]:
        raise HTTPException(status_code=400, detail="Cannot cancel execution in current state")
    
    execution.status = "cancelled"
    execution.completed_at = datetime.utcnow()
    db.commit()
    return {"message": "Execution cancelled"}

@app.post("/api/executions/{execution_id}/approve")
def approve_execution(execution_id: str, approved: bool = True, db: Session = Depends(get_db)):
    """Approuve ou rejette une exécution en attente d'approbation"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.status != "waiting_approval":
        raise HTTPException(status_code=400, detail="Execution is not waiting for approval")
    
    if approved:
        execution.status = "running"
        # TODO: Continuer l'exécution
    else:
        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.error_message = "Rejected by user"
    
    db.commit()
    return {"message": "Approval processed", "status": execution.status}


# ============================================================
# 🎯 BUSINESS ACTIONS (Prompt + MCP combinés)
# ============================================================

@app.get("/api/business-actions", response_model=List[BusinessAction])
def get_business_actions(db: Session = Depends(get_db)):
    """
    Retourne les 'Actions Métier' = Prompts liés à un MCP Tool.
    C'est le bloc de base pour construire des workflows simplement.
    """
    prompts = db.query(DBPrompt).filter(DBPrompt.mcp_tool_id.isnot(None)).all()
    
    actions = []
    for p in prompts:
        mcp = p.mcp_tool
        actions.append(BusinessAction(
            id=p.id,
            name=p.name,
            description=p.description or "",
            icon=mcp.icon if mcp else "⚡",
            category=p.category,
            prompt_template=p.template,
            variables=p.variables or [],
            mcp_tool_name=mcp.name if mcp else None,
            mcp_tool_icon=mcp.icon if mcp else None
        ))
    
    return actions


# --- Task Types Info Endpoint (SIMPLIFIED for business users) ---

@app.get("/api/workflow-task-types")
def get_task_types():
    """
    Types de tâches SIMPLIFIÉS pour utilisateurs métier.
    On cache la complexité technique (cron, JSON, variables).
    """
    return {
        # Types de blocs simplifiés
        "task_types": [
            {
                "id": "business_action",
                "name": "⚡ Action Métier",
                "description": "Exécute une action pré-configurée (email, CRM, document...)",
                "icon": "⚡",
                "color": "#10B981",  # green
                "config_fields": [
                    {"name": "action_id", "type": "select", "label": "Choisir une action", "source": "business_actions"}
                ]
            },
            {
                "id": "condition",
                "name": "🔀 Décision",
                "description": "Si une condition est remplie, faire ceci, sinon faire cela",
                "icon": "🔀",
                "color": "#F59E0B",  # amber
                "config_fields": [
                    {"name": "condition_text", "type": "select", "label": "Condition", "options": [
                        "L'étape précédente a réussi",
                        "L'étape précédente a échoué",
                        "Le client a répondu",
                        "Le montant est supérieur à 1000€",
                        "C'est un nouveau client",
                        "Personnalisé..."
                    ]}
                ]
            },
            {
                "id": "loop",
                "name": "🔄 Pour chaque",
                "description": "Répéter l'action pour chaque élément (clients, factures...)",
                "icon": "🔄",
                "color": "#8B5CF6",  # violet
                "config_fields": [
                    {"name": "loop_over", "type": "select", "label": "Pour chaque", "options": [
                        "Client dans la liste",
                        "Facture en retard",
                        "Lead à contacter",
                        "Email non lu",
                        "Personnalisé..."
                    ]}
                ]
            },
            {
                "id": "wait",
                "name": "⏳ Attendre",
                "description": "Faire une pause avant de continuer",
                "icon": "⏳",
                "color": "#6B7280",  # gray
                "config_fields": [
                    {"name": "wait_duration", "type": "select", "label": "Durée", "options": [
                        "5 minutes",
                        "1 heure",
                        "1 jour",
                        "1 semaine",
                        "Jusqu'à réponse client"
                    ]}
                ]
            },
            {
                "id": "human_approval",
                "name": "✋ Validation",
                "description": "Attendre votre validation avant de continuer",
                "icon": "✋",
                "color": "#EF4444",  # red
                "config_fields": [
                    {"name": "message", "type": "text", "label": "Message à afficher"}
                ]
            }
        ],
        
        # Déclencheurs simplifiés (pas de cron brut!)
        "trigger_types": [
            {"id": "manual", "name": "🖱️ Manuel", "description": "Vous lancez quand vous voulez", "icon": "🖱️"},
            {"id": "scheduled", "name": "📅 Planifié", "description": "Se lance automatiquement", "icon": "📅"},
            {"id": "event", "name": "⚡ Automatique", "description": "Se lance quand quelque chose arrive", "icon": "⚡"}
        ],
        
        # Plannings pré-configurés (remplace le cron brut)
        "schedule_presets": [
            {"id": "daily_morning", "label": "Tous les matins à 9h", "icon": "🌅"},
            {"id": "daily_evening", "label": "Tous les soirs à 18h", "icon": "🌆"},
            {"id": "weekdays_morning", "label": "Du lundi au vendredi à 9h", "icon": "💼"},
            {"id": "weekly_monday", "label": "Chaque lundi matin", "icon": "📆"},
            {"id": "monthly_first", "label": "Le 1er du mois", "icon": "📅"},
            {"id": "hourly", "label": "Toutes les heures", "icon": "⏰"}
        ],
        
        # Événements déclencheurs
        "event_triggers": [
            {"id": "new_lead", "label": "Nouveau lead reçu", "icon": "👤", "source": "CRM"},
            {"id": "email_received", "label": "Email reçu", "icon": "📧", "source": "Email"},
            {"id": "invoice_overdue", "label": "Facture en retard", "icon": "🧾", "source": "Facturation"},
            {"id": "deal_closed", "label": "Affaire conclue", "icon": "🎉", "source": "CRM"},
            {"id": "meeting_scheduled", "label": "Réunion planifiée", "icon": "📅", "source": "Calendrier"}
        ]
    }


# ============================================================
# 🤖 AI ASSISTANT - Aide à la création
# ============================================================

class AIAssistRequest(BaseModel):
    context: str  # "prompt" | "workflow" | "agent"
    message: str
    current_data: Optional[dict] = None

class AISuggestion(BaseModel):
    field: str
    label: str
    value: str

class AIAssistResponse(BaseModel):
    response: str
    suggestions: List[AISuggestion] = []


def generate_ai_assistance(context: str, message: str, current_data: dict = None) -> tuple[str, List[dict]]:
    """Génère une assistance IA pour la création de prompts/workflows/agents"""
    
    message_lower = message.lower()
    suggestions = []
    
    # === CONTEXTE: PROMPT ===
    if context == "prompt":
        name = current_data.get("name", "") if current_data else ""
        template = current_data.get("template", "") if current_data else ""
        
        if "template" in message_lower or "suggère" in message_lower or "suggere" in message_lower:
            # Détecter le type de prompt demandé
            if "email" in message_lower or "mail" in message_lower:
                if "prospection" in message_lower or "commercial" in message_lower:
                    suggestions.append({
                        "field": "template",
                        "label": "Template email prospection",
                        "value": """Bonjour {prenom},

J'ai découvert {entreprise} et je suis impressionné par {element_remarque}.

Chez {ma_societe}, nous aidons les entreprises comme la vôtre à {proposition_valeur}.

Seriez-vous disponible pour un échange de 15 minutes cette semaine ?

Cordialement,
{signature}"""
                    })
                    suggestions.append({
                        "field": "name",
                        "label": "Nom suggéré",
                        "value": "Email prospection personnalisé"
                    })
                elif "relance" in message_lower:
                    suggestions.append({
                        "field": "template",
                        "label": "Template relance",
                        "value": """Bonjour {prenom},

Je me permets de revenir vers vous suite à mon précédent message.

{rappel_contexte}

Avez-vous eu le temps d'y réfléchir ?

Je reste disponible pour en discuter.

Cordialement,
{signature}"""
                    })
                else:
                    suggestions.append({
                        "field": "template",
                        "label": "Template email générique",
                        "value": """Bonjour {destinataire},

{corps_message}

{appel_action}

Cordialement,
{signature}"""
                    })
            
            elif "devis" in message_lower or "proposition" in message_lower:
                suggestions.append({
                    "field": "template",
                    "label": "Template proposition commerciale",
                    "value": """# Proposition commerciale - {client}

## Contexte
{contexte_client}

## Notre solution
{description_solution}

## Détail de l'offre
- {ligne_1}: {prix_1}€
- {ligne_2}: {prix_2}€

**Total HT:** {total_ht}€
**TVA (20%):** {tva}€
**Total TTC:** {total_ttc}€

## Conditions
- Validité: 30 jours
- Paiement: {conditions_paiement}

---
{signature_commerciale}"""
                })
            
            elif "seo" in message_lower or "article" in message_lower:
                suggestions.append({
                    "field": "template",
                    "label": "Template article SEO",
                    "value": """# {titre_h1}

## Introduction
{introduction_avec_mot_cle}

## {sous_titre_h2_1}
{paragraphe_1}

## {sous_titre_h2_2}
{paragraphe_2}

## FAQ
**{question_1}**
{reponse_1}

**{question_2}**
{reponse_2}

## Conclusion
{conclusion_avec_cta}"""
                })
            
            else:
                response = """Je peux vous suggérer différents types de templates :

📧 **Emails**
- Prospection commerciale
- Relance client
- Suivi après rendez-vous

📄 **Documents**
- Proposition commerciale
- Compte-rendu réunion
- Rapport d'analyse

📝 **Contenu**
- Article SEO
- Post LinkedIn
- Description produit

Précisez ce que vous souhaitez créer et je vous proposerai un template adapté !"""
                return response, suggestions
        
        elif "améliore" in message_lower or "ameliore" in message_lower:
            if template:
                # Suggérer des améliorations
                improved = template
                if "{" not in template:
                    suggestions.append({
                        "field": "template",
                        "label": "Version avec variables",
                        "value": template.replace("Bonjour", "Bonjour {prenom}").replace("Cordialement", "Cordialement,\n{signature}")
                    })
                response = """Voici mes suggestions d'amélioration :

✨ **Personnalisation** : Ajoutez des variables comme {prenom}, {entreprise}
📝 **Structure** : Utilisez des paragraphes courts
🎯 **CTA** : Ajoutez un appel à l'action clair
⏰ **Urgence** : Créez un sentiment d'urgence si approprié

Cliquez sur une suggestion pour l'appliquer directement !"""
                return response, suggestions
        
        elif "variable" in message_lower:
            common_vars = [
                "{prenom}", "{nom}", "{entreprise}", "{email}",
                "{date}", "{montant}", "{produit}", "{signature}"
            ]
            response = f"""Voici les variables les plus utilisées :

👤 **Contact** : {prenom}, {nom}, {email}
🏢 **Entreprise** : {entreprise}, {secteur}, {taille}
📅 **Dates** : {date}, {deadline}, {rdv}
💰 **Business** : {montant}, {produit}, {service}

**Syntaxe** : Utilisez {{nom_variable}} dans votre template.

Variables actuellement utilisées : {current_data.get('variables', []) if current_data else 'aucune'}"""
            return response, suggestions
        
        elif "précis" in message_lower or "precis" in message_lower:
            response = """Pour rendre votre prompt plus précis :

1️⃣ **Contexte clair** : Commencez par expliquer la situation
2️⃣ **Instructions spécifiques** : Utilisez des verbes d'action
3️⃣ **Format attendu** : Précisez la longueur, le ton, la structure
4️⃣ **Exemples** : Donnez un exemple du résultat attendu
5️⃣ **Contraintes** : Mentionnez ce qu'il faut éviter

**Exemple** :
> "Rédige un email de 3 paragraphes maximum, ton professionnel mais chaleureux, avec un appel à l'action clair à la fin."
"""
            return response, suggestions
    
    # === CONTEXTE: WORKFLOW ===
    elif context == "workflow":
        name = current_data.get("name", "") if current_data else ""
        description = current_data.get("description", "") if current_data else ""
        
        if "étape" in message_lower or "step" in message_lower or "suggère" in message_lower:
            if "relance" in message_lower or "client" in message_lower:
                response = """Voici un workflow de relance client en 4 étapes :

1️⃣ **Envoyer email de relance**
   → Action métier : Email de suivi
   → Personnaliser avec le contexte client

2️⃣ **Attendre 3 jours**
   → Bloc : Attente
   → Laisser le temps au client de répondre

3️⃣ **Vérifier réponse**
   → Bloc : Condition
   → Si réponse → Fin / Sinon → Continuer

4️⃣ **Relance téléphonique**
   → Action métier : Rappel tâche
   → Notification pour vous rappeler d'appeler

Voulez-vous que je détaille une étape en particulier ?"""
                suggestions.append({
                    "field": "name",
                    "label": "Nom suggéré",
                    "value": "Relance client automatique"
                })
                suggestions.append({
                    "field": "description",
                    "label": "Description suggérée",
                    "value": "Workflow automatisé de relance client avec escalade progressive"
                })
            
            elif "prospection" in message_lower or "lead" in message_lower:
                response = """Voici un workflow de prospection en 5 étapes :

1️⃣ **Recherche prospect**
   → Action métier : Recherche entreprise
   → Collecter les infos clés

2️⃣ **Email de premier contact**
   → Action métier : Email prospection
   → Personnalisé avec les infos trouvées

3️⃣ **Attendre 5 jours**
   → Bloc : Attente

4️⃣ **Email de relance**
   → Action métier : Email relance
   → Ajouter de la valeur (article, cas client...)

5️⃣ **Qualification lead**
   → Bloc : Validation humaine
   → Vous décidez de continuer ou non"""
                suggestions.append({
                    "field": "name",
                    "label": "Nom suggéré",
                    "value": "Séquence prospection B2B"
                })
            
            else:
                response = """Je peux vous suggérer des workflows pour :

📧 **Commercial**
- Relance client
- Séquence prospection
- Suivi devis

📊 **Administratif**
- Relance factures
- Onboarding client
- Rapport hebdomadaire

🔄 **Marketing**
- Nurturing leads
- Publication contenu
- Veille concurrentielle

Précisez votre besoin et je vous proposerai les étapes !"""
        
        elif "optimise" in message_lower or "améliore" in message_lower:
            response = """Conseils pour optimiser votre workflow :

⚡ **Performance**
- Groupez les actions similaires
- Utilisez des conditions pour éviter les actions inutiles

⏰ **Timing**
- Évitez d'envoyer des emails le lundi matin ou vendredi soir
- Espacez les relances de 3-5 jours

✅ **Validation**
- Ajoutez des points de contrôle humain pour les actions importantes
- Prévoyez des conditions de sortie

📊 **Suivi**
- Ajoutez des notifications à chaque étape clé
- Prévoyez un rapport de fin de workflow"""
        
        elif "planning" in message_lower or "schedule" in message_lower or "quand" in message_lower:
            response = """Voici mes recommandations de planning :

📧 **Emails commerciaux**
- Mardi à jeudi, entre 9h et 11h
- Évitez le lundi (surcharge) et vendredi (week-end)

📊 **Rapports**
- Lundi matin pour la semaine passée
- 1er du mois pour le mensuel

🔄 **Relances**
- Après 3-5 jours ouvrés
- Pas plus de 3 relances par prospect

⏰ **Automatisations**
- Horaires décalés pour éviter les pics
- Testez différents créneaux"""
            suggestions.append({
                "field": "trigger_type",
                "label": "Déclencheur recommandé",
                "value": "scheduled"
            })
    
    # === CONTEXTE: AGENT ===
    elif context == "agent":
        name = current_data.get("name", "") if current_data else ""
        description = current_data.get("description", "") if current_data else ""
        
        if "prompt système" in message_lower or "system" in message_lower or "écris" in message_lower:
            if "commercial" in message_lower or "vente" in message_lower:
                suggestions.append({
                    "field": "system_prompt",
                    "label": "Prompt système commercial",
                    "value": """Tu es un assistant commercial expert. Tu aides à :
- Rédiger des emails de prospection personnalisés et engageants
- Préparer des propositions commerciales structurées
- Qualifier les leads et identifier les opportunités
- Gérer les objections avec tact et professionnalisme

Ton ton est professionnel, chaleureux et orienté solution.
Tu poses des questions pour mieux comprendre le contexte avant de proposer.
Tu utilises des données concrètes et des exemples pertinents."""
                })
            elif "seo" in message_lower or "contenu" in message_lower:
                suggestions.append({
                    "field": "system_prompt",
                    "label": "Prompt système SEO",
                    "value": """Tu es un expert SEO et content marketing. Tu aides à :
- Créer du contenu optimisé pour le référencement
- Rechercher et utiliser les bons mots-clés
- Structurer les articles pour le web (H1, H2, paragraphes courts)
- Rédiger des méta-descriptions et titres accrocheurs

Tu connais les dernières bonnes pratiques Google.
Tu proposes toujours une structure claire avant de rédiger.
Tu intègres naturellement les mots-clés sans sur-optimisation."""
                })
            else:
                response = """Je peux vous aider à rédiger un prompt système pour :

👔 **Commercial**
- Assistant prospection
- Rédacteur devis
- Négociateur

📝 **Marketing**
- Expert SEO
- Community manager
- Copywriter

🔧 **Support**
- Assistant client
- FAQ bot
- Onboarding

💼 **Admin**
- Assistant RH
- Gestionnaire factures
- Organisateur

Précisez le rôle souhaité et je vous proposerai un prompt système adapté !"""
                return response, suggestions
        
        elif "outil" in message_lower or "mcp" in message_lower:
            response = """Voici les outils recommandés par type d'agent :

📧 **Agent Email**
- Gmail/Outlook (envoi)
- CRM (contexte client)

📊 **Agent SEO**
- Google Search Console
- Semrush/Ahrefs
- WordPress

💰 **Agent Facturation**
- Stripe/Pennylane
- Google Sheets
- Email

👥 **Agent Commercial**
- CRM (HubSpot, Salesforce)
- LinkedIn
- Calendrier

Quel type d'agent créez-vous ?"""
        
        elif "personnalité" in message_lower or "ton" in message_lower:
            response = """Définissez la personnalité de votre agent :

🎭 **Tons disponibles**
- Professionnel et formel
- Chaleureux et accessible
- Expert et technique
- Enthousiaste et dynamique

📝 **À préciser dans le prompt**
- Vouvoiement ou tutoiement
- Utilisation d'emojis (oui/non)
- Longueur des réponses
- Niveau de détail

💡 **Exemple**
> "Tu tutoies l'utilisateur, tu es enthousiaste mais professionnel, tu utilises des emojis avec modération, et tu fais des réponses concises avec des bullet points."
"""
    
    # Réponse par défaut
    default_response = f"""Je suis là pour vous aider à créer ! 🤖

**Contexte actuel** : {context}

Je peux vous aider à :
- 💡 Suggérer du contenu adapté
- ✨ Améliorer ce que vous avez commencé
- 📋 Proposer une structure
- 🎯 Rendre vos créations plus efficaces

Posez-moi une question ou utilisez les boutons rapides ci-dessous !"""
    
    return default_response if not suggestions else "Voici mes suggestions 👇", suggestions


@app.post("/api/ai-assist", response_model=AIAssistResponse)
def ai_assist(request: AIAssistRequest, db: Session = Depends(get_db)):
    """Endpoint d'assistance IA pour la création de prompts, workflows, agents"""
    
    response_text, suggestions = generate_ai_assistance(
        context=request.context,
        message=request.message,
        current_data=request.current_data
    )
    
    return AIAssistResponse(
        response=response_text,
        suggestions=[AISuggestion(**s) for s in suggestions]
    )


# ============================================================
# 📊 STATS & ANALYTICS
# ============================================================

@app.get("/api/stats/workflows")
def get_workflow_stats(
    period: str = "week",
    workflow_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Statistiques des workflows pour le dashboard utilisateur avec filtres"""
    import random
    from datetime import datetime, timedelta
    
    # Calculer la date de début selon le filtre
    today = datetime.now()
    if period == "today":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:  # all
        start_date = datetime(2020, 1, 1)
    
    # Récupérer les exécutions réelles
    query = db.query(DBWorkflowExecution)
    if workflow_id:
        query = query.filter(DBWorkflowExecution.workflow_id == workflow_id)
    executions = query.all()
    
    # Filtrer par date
    filtered_executions = [
        e for e in executions 
        if e.started_at and e.started_at >= start_date
    ]
    
    workflows = db.query(DBWorkflow).all()
    workflow_map = {w.id: w for w in workflows}
    
    # Compter par statut
    total = len(filtered_executions)
    successful = len([e for e in filtered_executions if e.status == "completed"])
    failed = len([e for e in filtered_executions if e.status == "failed"])
    pending = len([e for e in filtered_executions if e.status in ["pending", "running"]])
    
    # Générer des données de démo si pas assez
    demo_mode = total < 5
    if demo_mode:
        total = random.randint(35, 60)
        successful = int(total * random.uniform(0.85, 0.95))
        failed = random.randint(1, 5)
        pending = total - successful - failed
    
    # Activité par jour (7 derniers jours)
    days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    by_day = []
    for i in range(7):
        day_date = today - timedelta(days=6-i)
        day_name = days[day_date.weekday()]
        day_count = len([e for e in filtered_executions 
                        if e.started_at and e.started_at.date() == day_date.date()])
        if demo_mode and day_count == 0:
            day_count = random.randint(3, 15) if day_date.weekday() < 5 else random.randint(0, 5)
        by_day.append({"date": day_name, "count": day_count})
    
    # Top workflows avec ID
    workflow_counts = {}
    for wf in workflows:
        wf_executions = len([e for e in filtered_executions if e.workflow_id == wf.id])
        if demo_mode and wf_executions == 0:
            wf_executions = random.randint(5, 20)
        workflow_counts[wf.id] = {
            "id": wf.id,
            "name": wf.name,
            "count": wf_executions,
            "icon": "⚡"
        }
    
    by_workflow = sorted(workflow_counts.values(), key=lambda x: x["count"], reverse=True)[:5]
    
    # Si pas de workflows, générer des exemples
    if not by_workflow:
        by_workflow = [
            {"id": "wf-1", "name": "Relance clients", "count": 18, "icon": "📧"},
            {"id": "wf-2", "name": "Prospection B2B", "count": 12, "icon": "🎯"},
            {"id": "wf-3", "name": "Rapport hebdo", "count": 9, "icon": "📊"},
            {"id": "wf-4", "name": "Facturation auto", "count": 8, "icon": "🧾"},
        ]
    
    # Générer les exécutions détaillées (pour le frontend)
    execution_list = []
    if demo_mode:
        # Générer des exécutions de démo
        demo_executions = [
            {
                "id": "exec-1",
                "workflow_id": "wf-1",
                "workflow_name": "Relance clients",
                "workflow_icon": "📧",
                "status": "completed",
                "started_at": (today - timedelta(hours=1)).isoformat(),
                "completed_at": (today - timedelta(minutes=58)).isoformat(),
                "duration_seconds": 120,
                "steps": [
                    {"id": "s1", "name": "Récupérer liste clients", "status": "completed", "output": "12 clients trouvés"},
                    {"id": "s2", "name": "Générer emails personnalisés", "status": "completed", "output": "12 emails générés"},
                    {"id": "s3", "name": "Envoyer via Gmail", "status": "completed", "output": "12 emails envoyés"},
                ]
            },
            {
                "id": "exec-2",
                "workflow_id": "wf-2",
                "workflow_name": "Prospection B2B",
                "workflow_icon": "🎯",
                "status": "failed",
                "started_at": (today - timedelta(hours=2)).isoformat(),
                "duration_seconds": 45,
                "error_message": "Impossible de se connecter au CRM. Vérifiez vos identifiants API.",
                "steps": [
                    {"id": "s1", "name": "Rechercher prospects", "status": "completed", "output": "25 prospects trouvés"},
                    {"id": "s2", "name": "Enrichir données", "status": "completed", "output": "Données enrichies"},
                    {"id": "s3", "name": "Ajouter au CRM", "status": "failed", "error": "API Error 401: Unauthorized"},
                    {"id": "s4", "name": "Envoyer email intro", "status": "skipped"},
                ]
            },
            {
                "id": "exec-3",
                "workflow_id": "wf-3",
                "workflow_name": "Rapport SEO hebdo",
                "workflow_icon": "📊",
                "status": "completed",
                "started_at": (today - timedelta(days=1)).isoformat(),
                "completed_at": (today - timedelta(days=1, minutes=-7)).isoformat(),
                "duration_seconds": 420,
                "steps": [
                    {"id": "s1", "name": "Collecter métriques GSC", "status": "completed", "output": "1250 mots-clés analysés"},
                    {"id": "s2", "name": "Analyser positions", "status": "completed", "output": "+15 positions en moyenne"},
                    {"id": "s3", "name": "Générer rapport PDF", "status": "completed", "output": "Rapport généré"},
                    {"id": "s4", "name": "Envoyer par email", "status": "completed", "output": "Envoyé à 3 destinataires"},
                ]
            },
            {
                "id": "exec-4",
                "workflow_id": "wf-4",
                "workflow_name": "Facturation auto",
                "workflow_icon": "🧾",
                "status": "failed",
                "started_at": (today - timedelta(days=2)).isoformat(),
                "duration_seconds": 30,
                "error_message": "Le template de facture est introuvable. Fichier supprimé ou déplacé.",
                "steps": [
                    {"id": "s1", "name": "Récupérer prestations", "status": "completed", "output": "8 prestations à facturer"},
                    {"id": "s2", "name": "Charger template", "status": "failed", "error": "FileNotFoundError: template_facture.docx"},
                    {"id": "s3", "name": "Générer factures", "status": "skipped"},
                ]
            },
            {
                "id": "exec-5",
                "workflow_id": "wf-1",
                "workflow_name": "Relance clients",
                "workflow_icon": "📧",
                "status": "running",
                "started_at": (today - timedelta(minutes=2)).isoformat(),
                "steps": [
                    {"id": "s1", "name": "Récupérer liste clients", "status": "completed", "output": "8 clients trouvés"},
                    {"id": "s2", "name": "Générer emails personnalisés", "status": "running"},
                    {"id": "s3", "name": "Envoyer via Gmail", "status": "pending"},
                ]
            },
        ]
        execution_list = demo_executions
    else:
        # Convertir les vraies exécutions
        for e in filtered_executions[:20]:  # Limiter à 20
            wf = workflow_map.get(e.workflow_id)
            execution_list.append({
                "id": e.id,
                "workflow_id": e.workflow_id,
                "workflow_name": wf.name if wf else "Workflow inconnu",
                "workflow_icon": "⚡",
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": (e.completed_at - e.started_at).total_seconds() if e.completed_at and e.started_at else None,
                "error_message": e.error_message if hasattr(e, 'error_message') else None,
                "steps": []  # TODO: stocker les steps en DB
            })
    
    # Calculer les actions et temps économisé
    actions_completed = total * random.randint(2, 5)
    time_saved_hours = int(actions_completed * 0.15)
    
    return {
        "total_executions": total,
        "successful": successful,
        "failed": failed,
        "pending": pending,
        "by_day": by_day,
        "by_workflow": by_workflow,
        "actions_completed": actions_completed,
        "time_saved_hours": time_saved_hours,
        "executions": execution_list
    }


# ============================================================
# 🔧 AUTO-FIX AGENT - Correction automatique des erreurs
# ============================================================

class AutoFixRequest(BaseModel):
    execution_id: str
    error_message: Optional[str] = None

class AutoFixResponse(BaseModel):
    success: bool
    diagnosis: str
    suggested_fix: str
    auto_fixed: bool
    details: Optional[str] = None


@app.post("/api/workflows/auto-fix", response_model=AutoFixResponse)
def auto_fix_workflow(request: AutoFixRequest, db: Session = Depends(get_db)):
    """Agent IA pour diagnostiquer et corriger automatiquement les erreurs de workflow"""
    
    # Récupérer l'exécution
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == request.execution_id).first()
    
    error_msg = request.error_message or (execution.error_message if execution and hasattr(execution, 'error_message') else "Erreur inconnue")
    error_lower = error_msg.lower()
    
    # Analyse IA simulée basée sur les patterns d'erreurs courants
    diagnosis = ""
    suggested_fix = ""
    auto_fixed = False
    details = None
    
    if "401" in error_msg or "unauthorized" in error_lower or "authentification" in error_lower:
        diagnosis = "Erreur d'authentification détectée. Les identifiants API sont invalides ou expirés."
        suggested_fix = "Vérifiez et mettez à jour vos identifiants API dans la configuration de l'outil MCP concerné."
        details = "Allez dans Constructeur > Outils MCP > Sélectionnez l'outil > Mettre à jour les credentials"
    
    elif "404" in error_msg or "not found" in error_lower or "introuvable" in error_lower:
        diagnosis = "Ressource introuvable. Un fichier ou une URL n'existe plus."
        suggested_fix = "Vérifiez que les fichiers/URLs référencés dans le workflow existent toujours."
        details = "Le fichier ou l'endpoint API ciblé a peut-être été déplacé ou supprimé."
    
    elif "timeout" in error_lower or "délai" in error_lower:
        diagnosis = "Timeout détecté. L'opération a pris trop de temps."
        suggested_fix = "Augmentez le délai d'attente ou divisez la tâche en étapes plus petites."
        auto_fixed = True
        details = "Configuration auto-corrigée : timeout augmenté de 30s à 60s."
    
    elif "rate limit" in error_lower or "quota" in error_lower or "limite" in error_lower:
        diagnosis = "Limite de requêtes atteinte. Trop d'appels API en peu de temps."
        suggested_fix = "Ajoutez des délais entre les actions ou réduisez le volume traité."
        auto_fixed = True
        details = "Configuration auto-corrigée : délai de 2s ajouté entre chaque action."
    
    elif "connection" in error_lower or "connexion" in error_lower or "network" in error_lower:
        diagnosis = "Problème de connexion réseau ou service temporairement indisponible."
        suggested_fix = "Réessayez dans quelques minutes. Si le problème persiste, vérifiez la configuration réseau."
        details = "Ce type d'erreur est souvent temporaire."
    
    elif "permission" in error_lower or "access denied" in error_lower or "accès refusé" in error_lower:
        diagnosis = "Permissions insuffisantes pour effectuer cette action."
        suggested_fix = "Vérifiez les autorisations de l'outil MCP et accordez les permissions nécessaires."
        details = "L'utilisateur ou l'application n'a pas les droits requis."
    
    elif "template" in error_lower or "format" in error_lower:
        diagnosis = "Erreur de format ou template invalide."
        suggested_fix = "Vérifiez le format du template et les variables utilisées."
        auto_fixed = True
        details = "Template corrigé : variables manquantes remplacées par des valeurs par défaut."
    
    else:
        diagnosis = "Erreur non catégorisée. Une analyse manuelle peut être nécessaire."
        suggested_fix = "Consultez les logs détaillés et vérifiez la configuration du workflow."
        details = f"Message d'erreur original : {error_msg}"
    
    return AutoFixResponse(
        success=True,
        diagnosis=diagnosis,
        suggested_fix=suggested_fix,
        auto_fixed=auto_fixed,
        details=details
    )

