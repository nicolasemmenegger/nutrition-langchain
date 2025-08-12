from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import secrets, os

class Settings(BaseSettings):
    # Load environment from a local .env file if present
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    app_name: str = "Lazy Nutri Coach API"
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
    database_url: str = "sqlite:///./nutri.db"
    jwt_secret: str = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
    jwt_algo: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # OpenAI
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str | None = os.getenv("OPENAI_MODEL", "gpt-4o")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")

    # Data paths
    kb_dir: str = "data/knowledge_base"
    chroma_dir: str = "data/.chroma"
    foods_csv: str = "data/foods.csv"
    uploads_dir: str = "data/uploads"

    # CORS
    cors_allow_all: bool = True

settings = Settings()
