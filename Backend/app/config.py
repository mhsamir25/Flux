from pydantic_settings import BaseSettings, SettingsConfigDict


# Settings model that reads from environment and .env file
class Settings(BaseSettings):
    # Async database URL; defaults to local PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/flux"

    # JWT signing secret; must be >=32 bytes to avoid PyJWT warnings
    jwt_secret: str = "dev-only-insecure-secret-override-via-env-CHANGE-ME"

    # Token lifetime in seconds (1 hour default)
    jwt_lifetime_seconds: int = 3600

    # Allowed CORS origins for frontend requests
    cors_origins: list[str] = ["http://localhost:5173"]

    # Configure settings source and behavior
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FLUX_", extra="ignore")


# Global settings instance used across the app
settings = Settings()
