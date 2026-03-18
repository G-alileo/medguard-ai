"""
Vector Store - ChromaDB interface for semantic search.
"""

from .chroma_client import ChromaClient, get_chroma_client

__all__ = [
    "ChromaClient",
    "get_chroma_client",
]
