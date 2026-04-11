from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wiki:wiki@localhost:5434/llm_wiki"
    jwt_secret: str = "change-me"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    cors_origins: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme"
    storage_path: str = "./data/uploads"
    default_llm_api_key: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
