from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import Field, model_validator
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


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_CORS_")
    origins: list[str] = ["http://localhost:3000"]
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class AzureAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_AZURE_AUTH_")
    use_default_credential: bool = True
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""


class EntraJWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_ENTRA_JWT_")
    enabled: bool = False
    tenant_id: str = "common"
    audience: str = "api://magenta-asoar"
    issuer: str = "https://login.microsoftonline.com/common/v2.0"


class SecurityHeadersSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SECURITY_HEADERS_")
    enabled: bool = True
    headers: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'",
        "X-XSS-Protection": "0",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }


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


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_TELEMETRY_")
    connection_string: Optional[str] = None
    otlp_endpoint: str = "http://tempo.magenta-observability:4317"
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True


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
    collectors_config_path: Path = Field(default=Path("soa/config/collectors.toml"))

    sql: SQLSettings = Field(default_factory=SQLSettings)
    elastic: ElasticSettings = Field(default_factory=ElasticSettings)
    lake: LakeSettings = Field(default_factory=LakeSettings)
    nosql: NoSQLSettings = Field(default_factory=NoSQLSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    security_headers: SecurityHeadersSettings = Field(default_factory=SecurityHeadersSettings)
    azure_auth: AzureAuthSettings = Field(default_factory=AzureAuthSettings)
    entra_jwt: EntraJWTSettings = Field(default_factory=EntraJWTSettings)
    eventhub: EventHubSettings = Field(default_factory=EventHubSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)

    @model_validator(mode="after")
    def validate_prod_db(self) -> "Settings":
        if self.env == "prod" and "sqlite" in self.sql.url:
            raise ValueError(
                "SQLite is not permitted in production. "
                "Set MAGENTA_SQL__URL to a PostgreSQL connection string."
            )
        return self

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
