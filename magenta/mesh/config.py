"""Data Mesh Configuration — Qdrant, OLLAMA, Redis connection settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class QdrantConfig:
    host: str = "localhost"
    port: int = 6334
    use_grpc: bool = True


@dataclass
class OllamaConfig:
    host: str = "http://localhost:11434"
    model: str = "bge-m3"
    dimension: int = 1024
    batch_size: int = 32


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    embedding_ttl: int = 86400


@dataclass
class ChunkingConfig:
    default_strategy: str = "semantic"
    default_chunk_size: int = 512
    default_overlap: int = 64


@dataclass
class SearchConfig:
    default_top_k: int = 10
    hybrid_enabled: bool = True
    rrf_k: int = 60


@dataclass
class MeshConfig:
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    collections_auto_create: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> MeshConfig:
        return cls(
            qdrant=QdrantConfig(
                host=os.getenv("MESH__QDRANT_HOST", "localhost"),
                port=int(os.getenv("MESH__QDRANT_PORT", "6334")),
                use_grpc=os.getenv("MESH__QDRANT_USE_GRPC", "true").lower() == "true",
            ),
            ollama=OllamaConfig(
                host=os.getenv("MESH__OLLAMA_HOST", "http://localhost:11434"),
                model=os.getenv("MESH__OLLAMA_MODEL", "bge-m3"),
                dimension=int(os.getenv("MESH__EMBEDDING_DIMENSION", "1024")),
                batch_size=int(os.getenv("MESH__OLLAMA_BATCH_SIZE", "32")),
            ),
            redis=RedisConfig(
                host=os.getenv("MESH__REDIS_HOST", "localhost"),
                port=int(os.getenv("MESH__REDIS_PORT", "6379")),
            ),
            collections_auto_create=(
                os.getenv("MESH__COLLECTIONS_AUTO_CREATE", "true").lower() == "true"
            ),
            log_level=os.getenv("MESH__LOG_LEVEL", "INFO"),
        )
