"""
Configuration centralisée avec variables d'environnement.
Utilise pydantic-settings pour la validation et les valeurs par défaut.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    """Configuration de l'application - chargée depuis les variables d'environnement"""
    
    # === Application ===
    APP_NAME: str = "Agent SaaS"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = Field(default=True)
    
    # === API ===
    API_PREFIX: str = "/api"
    ALLOWED_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])
    
    # === Database ===
    # SQLite pour dev, PostgreSQL pour prod
    DATABASE_URL: str = Field(default="sqlite:///./agent_saas.db")
    DATABASE_ECHO: bool = Field(default=False)  # Log SQL queries
    
    # === Redis (optionnel pour dev) ===
    REDIS_URL: str | None = Field(default=None)
    
    # === Security ===
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production-minimum-32-chars")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # === Password Hashing ===
    BCRYPT_ROUNDS: int = 12  # 12 pour prod, peut baisser pour les tests
    
    # === Rate Limiting ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100  # Requests per minute
    RATE_LIMIT_PERIOD: int = 60  # Seconds
    
    # === Email (optionnel) ===
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@agent-saas.com"
    
    # === LLM Providers ===
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    
    # === Stripe (Billing) ===
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_STARTER: str | None = None
    STRIPE_PRICE_BUSINESS: str | None = None
    STRIPE_PRICE_ENTERPRISE: str | None = None
    
    # === Feature Flags ===
    FEATURE_MFA_ENABLED: bool = False
    FEATURE_BILLING_ENABLED: bool = False
    FEATURE_EMAIL_VERIFICATION: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration - mise en cache"""
    return Settings()


# Export pour import facile
settings = get_settings()
