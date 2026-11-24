from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    saas_api_url: str = "http://127.0.0.1:8002"
    saas_api_token: str = ""
    acreditai_aprovadores: dict[str, str] = {}
    acreditai_db_path: str = "acreditai.db"
    http_timeout: float = 10.0
    max_creditos_operacao: int = 3000
    max_iteracoes_grafo: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
