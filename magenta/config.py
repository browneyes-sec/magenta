from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import Field
from typing import Literal, Optional
from pathlib import Path


class SQLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SQL_")
    url: str = "sqlite+aiosqlite:///data/magenta.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class ElasticSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_ELASTIC_")
    hosts: list[str] = ["http://localhost:9200"]
    username: Optional[str] = None
    password: Optional[str] = None
    index_prefix: str = "magenta"
    ilm_policy: str = "magenta-hot-warm-cold"


class LakeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_LAKE_")
    connection_string: Optional[str] = None
    container: str = "magenta-lake"
    root: str = "/data/magenta/lake"
    parquet_compression: str = "snappy"


class NoSQLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_NOSQL_")
    connection_string: Optional[str] = None
    database_name: str = "magenta"


class EventHubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_EVENTHUB_")
    connection_string: Optional[str] = None
    namespace: str = "magenta-agent-bus"
    topics: dict[str, str] = {
        "raw_alerts": "raw-alerts",
        "enriched_alerts": "enriched-alerts",
        "actions": "actions",
        "audit": "audit",
    }


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_MODELS_")
    default_provider: str = "ollama"
    default_model: str = "qwen2.5:7b"
    ollama_host: str = "http://localhost:11434"
    openrouter_key: Optional[str] = None
    gemini_key: Optional[str] = None
    groq_key: Optional[str] = None


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_GATEWAY_CACHE_")
    enabled: bool = True
    ttl_seconds: int = 3600
    min_similarity: float = 0.92


class RedactionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_GATEWAY_REDACTION_")
    enabled: bool = True
    default_fields: list[str] = ["usernames", "ips", "email_addresses"]


class AuditSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_GATEWAY_AUDIT_")
    enabled: bool = True
    batch_size: int = 10
    flush_interval_seconds: int = 5


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_GATEWAY_")
    enabled: bool = True
    mode: Literal["shadow", "enforcing"] = "shadow"
    policy_file: str = "config/llm-routing.yaml"
    redis_url: str = "redis://localhost:6379/0"
    cache: CacheSettings = Field(default_factory=CacheSettings)
    redaction: RedactionSettings = Field(default_factory=RedactionSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MAGENTA_",
        yaml_file="config/default.yaml",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: Literal["dev", "staging", "prod"] = "dev"
    verbose: bool = False
    quiet: bool = False
    format: Literal["text", "json"] = "text"

    data_dir: Path = Field(default=Path("data"))
    config_dir: Path = Field(default=Path("config"))

    sql: SQLSettings = Field(default_factory=SQLSettings)
    elastic: ElasticSettings = Field(default_factory=ElasticSettings)
    lake: LakeSettings = Field(default_factory=LakeSettings)
    nosql: NoSQLSettings = Field(default_factory=NoSQLSettings)
    eventhub: EventHubSettings = Field(default_factory=EventHubSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


settings = Settings()
