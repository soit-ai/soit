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

    project_name: str = "soit"
    """Project name."""
    project_description: str = "SOIT is a platform for llm application building."
    """Project description."""

    # Database
    database_type: str = "postgresql"
    """Database type."""
    database_host: str = "localhost"
    """Database host."""
    database_port: int = 5432
    """Database port."""
    database_user: Optional[str] = None
    """Database username."""
    database_pass: Optional[str] = None
    """Database password."""
    database_name: str = ""
    """Database name."""
    database_url: str = f"{database_type}://{database_user}:{database_pass}@{database_host}:{database_port}/{database_name}"
    """Database URL."""
    
    # Redis
    redis_host: str = "localhost"
    """Redis host."""
    redis_port: int = 6379
    """Redis port."""
    redis_pass: Optional[str] = None
    """Redis pass."""
    redis_db: int = 0
    """Redis data."""
    redis_url: str = f"redis://:{redis_pass}@{redis_host}:{redis_port}/{redis_db}"
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
    sentry_enabled: bool = False
    """Enable Sentry error tracking."""
    sentry_traces_sample_rate: float = 0.0
    """Sentry traces sample rate."""
    log_level: str = "INFO"
    """Log level (DEBUG, INFO, WARNING, ERROR)."""
    

    # Plugins
    plugins_dir: str = "./var/plugins"
    """Filesystem directory for plugin packages and extracted installs."""

    # Feature flags
    enable_egress_policy: bool = True
    """Enable egress policy (deny-by-default)."""
    
    # API
    api_v1_prefix: str = "/api/v1"
    """API v1 prefix."""


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Return global Settings instance."""
    return settings

