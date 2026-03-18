"""
ChromaDB Client - Vector store interface for semantic search.
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class ChromaClient:
    """
    Client for interacting with ChromaDB vector store.

    Provides semantic search capabilities for drug information.
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_prefix: Optional[str] = None,
    ):
        self.persist_directory = persist_directory or settings.CHROMADB_PATH
        self.collection_prefix = collection_prefix or settings.CHROMADB_COLLECTION_PREFIX

        self._client = None
        self._embedding_model = None
        self._collections = {}

    @property
    def client(self):
        """Lazy-load ChromaDB client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def embedding_model(self):
        """Lazy-load embedding model."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
            device = getattr(settings, "EMBEDDING_DEVICE", "cpu")

            logger.info(f"Loading embedding model: {model_name}")
            self._embedding_model = SentenceTransformer(model_name, device=device)

        return self._embedding_model

    def get_collection(self, name: str):
        """Get a ChromaDB collection."""
        full_name = f"{self.collection_prefix}{name}"

        if full_name not in self._collections:
            try:
                self._collections[full_name] = self.client.get_collection(name=full_name)
            except Exception:
                logger.warning(f"Collection {full_name} not found")
                return None

        return self._collections[full_name]

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a query."""
        embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    def search_similar(
        self,
        query: str,
        collection_name: str = "drug_labels",
        limit: int = 5,
        drug_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search across vector store.

        Args:
            query: Search query
            collection_name: Name of collection to search
            limit: Maximum results
            drug_filter: Optional drug name to filter results

        Returns:
            List of result dicts with text, metadata, and distance
        """
        collection = self.get_collection(collection_name)
        if collection is None:
            logger.warning(f"Collection {collection_name} not available")
            return []

        # Build where filter if drug specified
        where_filter = None
        if drug_filter:
            drug_lower = drug_filter.lower().strip()
            # Search in generic_names or brand_names metadata
            where_filter = {
                "$or": [
                    {"generic_names": {"$contains": drug_lower}},
                    {"brand_names": {"$contains": drug_lower}},
                    {"drug": drug_lower},
                    {"drug_a": drug_lower},
                    {"drug_b": drug_lower},
                ]
            }

        # Generate query embedding
        query_embedding = self.embed_query(query)

        # Search
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Search error: {e}")
            # Try without filter
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"],
            )

        # Format results
        formatted = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                    "id": results["ids"][0][i] if results.get("ids") else None,
                })

        return formatted

    def get_context_for_drug(
        self,
        drug: str,
        query_type: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Retrieve relevant context for a specific drug.

        Args:
            drug: Drug name
            query_type: Type of info needed ('interactions', 'side_effects', 'usage')
            limit: Maximum results per collection

        Returns:
            List of relevant context chunks
        """
        results = []

        # Build query based on type
        if query_type == "interactions":
            query = f"drug interactions warnings for {drug}"
            collections = ["drug_interactions", "drug_labels"]
        elif query_type == "side_effects":
            query = f"side effects adverse reactions of {drug}"
            collections = ["adverse_reactions", "drug_labels"]
        elif query_type == "usage":
            query = f"indications usage dosage for {drug}"
            collections = ["drug_labels"]
        else:
            query = f"information about {drug}"
            collections = ["drug_labels", "drug_interactions", "adverse_reactions"]

        # Search each collection
        for coll_name in collections:
            coll_results = self.search_similar(
                query=query,
                collection_name=coll_name,
                limit=limit,
                drug_filter=drug,
            )
            for r in coll_results:
                r["collection"] = coll_name
            results.extend(coll_results)

        # Sort by distance (smaller is better)
        results.sort(key=lambda x: x.get("distance", float("inf")))

        return results[:limit * 2]

    def search_interactions(
        self,
        drug1: str,
        drug2: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search for interaction information between drugs.

        Args:
            drug1: First drug name
            drug2: Second drug name (optional)
            limit: Maximum results

        Returns:
            List of relevant interaction context
        """
        if drug2:
            query = f"drug interaction between {drug1} and {drug2}"
        else:
            query = f"drug interactions with {drug1}"

        # Search interactions collection
        results = self.search_similar(
            query=query,
            collection_name="drug_interactions",
            limit=limit,
        )

        # Also search labels for interaction sections
        label_results = self.search_similar(
            query=query,
            collection_name="drug_labels",
            limit=limit,
            drug_filter=drug1,
        )

        # Filter label results to interaction sections
        filtered_labels = [
            r for r in label_results
            if r.get("metadata", {}).get("section") == "Drug Interactions"
        ]

        results.extend(filtered_labels)

        # Deduplicate and sort
        seen_texts = set()
        unique_results = []
        for r in results:
            text_hash = hash(r["text"][:200])
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.get("distance", float("inf")))
        return unique_results[:limit]

    def get_collection_stats(self) -> dict:
        """Get statistics about all collections."""
        stats = {}

        collection_names = ["drug_labels", "drug_interactions", "adverse_reactions"]

        for name in collection_names:
            collection = self.get_collection(name)
            if collection:
                stats[name] = {
                    "count": collection.count(),
                }
            else:
                stats[name] = {"count": 0, "exists": False}

        return stats


# Singleton instance
_chroma_client: Optional[ChromaClient] = None


def get_chroma_client() -> ChromaClient:
    """Get the global ChromaClient instance."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient()
    return _chroma_client
