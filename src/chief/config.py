from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "data/chief.db"
    chief_llm_provider: str = "cli"  # "cli" | "api", see llm/factory.py


settings = Settings()
