""" settings

Settings model and environment parsing.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/soit"
    """PostgreSQL database URL."""
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    """Redis URL for cache and message queue."""
    
    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    """Secret key for JWT token signing."""
    jwt_algorithm: str = "HS256"
    """JWT algorithm."""
    access_token_expire_minutes: int = 30
    """Access token expiration in minutes."""
    
    # Milvus
    milvus_host: str = "localhost"
    """Milvus host."""
    milvus_port: int = 19530
    """Milvus port."""
    
    # MinIO / S3
    minio_endpoint: Optional[str] = None
    """MinIO endpoint URL."""
    minio_access_key: Optional[str] = None
    """MinIO access key."""
    minio_secret_key: Optional[str] = None
    """MinIO secret key."""
    minio_bucket: str = "soit-artifacts"
    """Default bucket name."""
    minio_secure: bool = False
    """Use HTTPS for MinIO."""
    
    # Vault
    vault_url: Optional[str] = None
    """HashiCorp Vault URL."""
    vault_token: Optional[str] = None
    """Vault token."""
    
    # Observability
    sentry_dsn: Optional[str] = None
    """Sentry DSN for error tracking."""
    log_level: str = "INFO"
    """Log level (DEBUG, INFO, WARNING, ERROR)."""
    
    # Feature flags
    enable_egress_policy: bool = True
    """Enable egress policy (deny-by-default)."""
    
    # API
    api_v1_prefix: str = "/api/v1"
    """API v1 prefix."""


# Global settings instance
settings = Settings()
