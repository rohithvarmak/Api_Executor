# """Application-wide configuration loaded from environment variables or .env file."""
# from functools import lru_cache
# from pydantic import Field
# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     """Global settings object automatically loaded from environment vars or .env."""

#     # LLM settings
#     openai_api_key: str | None = Field(None, env="OPENAI_API_KEY")
#     anthropic_api_key: str | None = Field(None, env="ANTHROPIC_API_KEY")
#     llm_provider: str = Field("openai", env="LLM_PROVIDER", description="Which provider to use: openai or anthropic")
#     llm_model_name: str = Field("gpt-4o-mini", env="LLM_MODEL_NAME", description="Model to call")

#     # MongoDB
#     mongo_uri: str | None = Field(None, env="MONGO_URI", description="Mongo connection string, if set will enable persistence")

#     # General app settings
#     debug: bool = Field(False, env="DEBUG", description="Enable verbose logging")
#     api_timeout_seconds: int = Field(30, env="API_TIMEOUT_SECONDS", description="Timeout for outbound HTTP calls")

#     # Pydantic settings behaviour
#     model_config = SettingsConfigDict(
#         env_file=".env",
#         case_sensitive=True,
#         extra="ignore",
#     )


# @lru_cache
# def get_settings() -> Settings:
#     """Return a cached instance of Settings so that different modules share the same object."""
#     return Settings()


import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

for key in ["RATE_LIMIT", "RATE_LIMIT_WINDOW", "SESSION_EXPIRE_SECONDS"]:
    value = os.getenv(key)
    if value:
        os.environ[key] = value.split(" ")[0]

class Settings(BaseSettings):
    # Application Settings
    app_name: str = "API Executor"
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "gpt-4-1106-preview")
    
    # Redis Configuration
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    
    # GitHub API Configuration
    mongo_uri: str = os.getenv("MONGO_URI", "")
    
   
    # Rate Limiting
    api_timeout_seconds: int = int(30)  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()

# Validate required settings
if not settings.openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# @lru_cache
# def get_settings() -> Settings:
#     """Return a cached instance of Settings so that different modules share the same object."""
#     return Settings()