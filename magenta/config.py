from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource


class SQLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SQL_")
    url: str = "sqlite+aiosqlite:///data/magenta.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class ElasticSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_ELASTIC_")
    hosts: list[str] = ["http://localhost:9200"]
    username: str | None = None
    password: str | None = None
    index_prefix: str = "magenta"
    ilm_policy: str = "magenta-hot-warm-cold"


class LakeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_LAKE_")
    connection_string: str | None = None
    container: str = "magenta-lake"
    root: str = "/data/magenta/lake"
    parquet_compression: str = "snappy"


class NoSQLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_NOSQL_")
    connection_string: str | None = None
    database_name: str = "magenta"


class SOARSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SOAR_")
    host: str = "localhost"
    port: int = 443
    username: str = ""
    password: str = ""
    verify_ssl: bool = True
    ca_bundle_path: str = ""
    failure_threshold: int = 5
    reset_timeout: float = 30.0


class IdempotencySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_IDEMPOTENCY_")
    storage_connection_string: str | None = None
    table_name: str = "IdempotencyKeys"
    ttl_hours: int = 24


class DeltaLakeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_DELTA_")
    uri: str = "/data/magenta/delta"
    mode: str = "append"
    partition_by: list[str] = ["source_system"]


class SentinelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SENTINEL_")
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    workspace_id: str = ""


class SplunkSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_SPLUNK_")
    host: str = "localhost"
    port: int = 8089
    username: str = ""
    password: str = ""
    use_ssl: bool = True
    verify_ssl: bool = True
    ca_bundle_path: str = ""


class EventHubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_EVENTHUB_")
    connection_string: str | None = None
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
    openrouter_key: str | None = None
    gemini_key: str | None = None
    groq_key: str | None = None


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_CORS_")
    origins: list[str] = ["http://localhost:3000"]
    allow_credentials: bool = True
    allow_methods: list[str] = Field(default=["GET", "POST", "PUT", "DELETE", "PATCH"])
    allow_headers: list[str] = Field(default=["Authorization", "Content-Type", "X-Request-ID"])


class AzureAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAGENTA_AZURE_AUTH_")
    use_default_credential: bool = True
    tenant_id: str = ""
    client_id: str = ""
    client_secret: SecretStr = Field(default=SecretStr(""))


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
    connection_string: str | None = None
    otlp_endpoint: str = "http://tempo.magenta-observability:4317"
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True
    use_tls: bool = False


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
    soar: SOARSettings = Field(default_factory=SOARSettings)
    sentinel: SentinelSettings = Field(default_factory=SentinelSettings)
    splunk: SplunkSettings = Field(default_factory=SplunkSettings)
    idempotency: IdempotencySettings = Field(default_factory=IdempotencySettings)
    delta_lake: DeltaLakeSettings = Field(default_factory=DeltaLakeSettings)
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
