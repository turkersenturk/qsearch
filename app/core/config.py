"""Configuration module for application settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant Configuration
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "documents"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"

    # Shared temp directory for file uploads (Docker volume)
    shared_temp_dir: str = "/tmp"  # Default to /tmp, override in Docker

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
