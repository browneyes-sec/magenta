"""Magenta Data Mesh — Vectorized semantic layer for agent memory and context."""

from magenta.mesh.gateway import MeshGateway
from magenta.mesh.memory import MemoryMCPServer
from magenta.mesh.pipeline import VectorizationPipeline

__all__ = [
    "MemoryMCPServer",
    "VectorizationPipeline",
    "MeshGateway",
]
