from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "app"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    crosscheck_min_block_tokens: int = 4
    crosscheck_merge_gap_tokens: int = 3
    crosscheck_boilerplate_doc_ratio: float = 0.6
    crosscheck_min_docs_for_boilerplate: int = 5
    crosscheck_threshold_pct: float = 25.0
    crosscheck_max_matches: int = 5

    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
