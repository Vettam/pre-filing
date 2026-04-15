from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    APP_NAME: str = "VettamAI Prefiling"
    APP_VERSION: str = "1.0.1"
    CORS_ALLOW_ORIGINS: list[str] = ["*"]
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    JWT_ALGORITHM: str = "ES256"
    JWT_AUDIENCE: str = "authenticated"
    SUPABASE_PROJECT_URL: str = ""
    SUPABASE_PROJECT_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_PREFILING_STORAGE_BUCKET: str = ""
    APP_HOST: str = "api.vettam.app"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

config = Settings()
