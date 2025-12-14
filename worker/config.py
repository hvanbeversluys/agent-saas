"""
Worker Configuration - Environment-based settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Worker service configuration."""
    
    # === Service Info ===
    SERVICE_NAME: str = "agent-saas-worker"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_DB: int = 0
    REDIS_STATE_DB: int = 1
    
    # === Database (read-only) ===
    DATABASE_URL: str = "sqlite:///./agent_saas.db"
    
    # === LLM Providers ===
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # === Worker Settings ===
    MAX_JOBS: int = 10  # Concurrent jobs
    JOB_TIMEOUT: int = 300  # 5 minutes default
    HEALTH_CHECK_PORT: int = 8001
    
    # === LangGraph Settings ===
    LANGGRAPH_CHECKPOINT_NS: str = "agent-saas"
    MAX_ITERATIONS: int = 25  # Max agent iterations
    
    # === Retry Settings ===
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # seconds
    
    # === Backend API (for callbacks) ===
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
