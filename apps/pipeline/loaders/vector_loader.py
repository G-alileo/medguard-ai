import gc
import logging
from pathlib import Path
from typing import Optional

from django.conf import settings
from tqdm import tqdm

logger = logging.getLogger(__name__)


class VectorLoader:

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

            logger.info(f"Loading embedding model: {model_name} on {device}")
            self._embedding_model = SentenceTransformer(model_name, device=device)

        return self._embedding_model

    def get_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        full_name = f"{self.collection_prefix}{name}"

        if full_name not in self._collections:
            self._collections[full_name] = self.client.get_or_create_collection(
                name=full_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[full_name]

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:

        if not texts:
            return []

        embeddings = self.embedding_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        return embeddings.tolist()

    def chunk_label_text(self, label: dict, max_chunk_size: int = 1500) -> list[dict]:

        chunks = []

        openfda = label.get("openfda", {})
        brand_names = openfda.get("brand_name", [])[:5]
        generic_names = openfda.get("generic_name", [])[:5]
        label_id = label.get("id", "unknown")

        # Sections to process (in order of importance)
        sections = [
            ("drug_interactions", "Drug Interactions"),
            ("contraindications", "Contraindications"),
            ("warnings_and_cautions", "Warnings and Precautions"),
            ("boxed_warning", "Boxed Warning"),
            ("adverse_reactions", "Adverse Reactions"),
            ("indications_and_usage", "Indications and Usage"),
            ("overdosage", "Overdosage"),
        ]

        for field_name, section_name in sections:
            content_list = label.get(field_name, [])
            if not content_list:
                continue

            text = content_list[0] if isinstance(content_list, list) else str(content_list)
            if not text or len(text.strip()) < 50:
                continue

            # Split into smaller chunks if needed
            text_chunks = self._split_text(text, max_chunk_size)

            for i, chunk_text in enumerate(text_chunks):
                chunk_id = f"{label_id}_{field_name}_{i}"

                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "label_id": label_id,
                        "section": section_name,
                        "brand_names": ", ".join(brand_names) if brand_names else "",
                        "generic_names": ", ".join(generic_names) if generic_names else "",
                        "chunk_index": i,
                        "source": "fda_label",
                    },
                })

        return chunks

    def _split_text(self, text: str, max_size: int, overlap: int = 100) -> list[str]:

        if len(text) <= max_size:
            return [text.strip()]

        chunks = []
        start = 0

        while start < len(text):
            end = start + max_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for period, question mark, or newline
                for sep in [". ", ".\n", "? ", "?\n", "\n\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + max_size // 2:
                        end = last_sep + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - overlap if end < len(text) else len(text)

        return chunks

    def load_drug_labels(self, show_progress: bool = True) -> dict:

        from pipeline.processing import DataUnifier

        stats = {"labels_processed": 0, "chunks_created": 0, "errors": 0}

        collection = self.get_collection("drug_labels")
        unifier = DataUnifier()

        logger.info("Loading drug labels into vector store...")

        # Buffer for batch insertion
        chunk_buffer = []
        buffer_limit = 100

        labels = list(unifier.iter_openfda_labels())
        iterator = tqdm(labels, desc="Vectorizing labels") if show_progress else labels

        for label in iterator:
            try:
                chunks = self.chunk_label_text(label)

                for chunk in chunks:
                    chunk_buffer.append(chunk)

                    if len(chunk_buffer) >= buffer_limit:
                        self._insert_chunks(collection, chunk_buffer)
                        stats["chunks_created"] += len(chunk_buffer)
                        chunk_buffer = []

                stats["labels_processed"] += 1

            except Exception as e:
                logger.error(f"Error processing label: {e}")
                stats["errors"] += 1

        # Insert remaining chunks
        if chunk_buffer:
            self._insert_chunks(collection, chunk_buffer)
            stats["chunks_created"] += len(chunk_buffer)

        logger.info(f"Drug labels loaded: {stats}")
        return stats

    def _insert_chunks(self, collection, chunks: list[dict]):
        """Insert a batch of chunks into a collection."""
        if not chunks:
            return

        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Generate embeddings
        embeddings = self.embed_texts(texts)

        # Insert into ChromaDB
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        # Cleanup
        gc.collect()

    def load_interactions(self, show_progress: bool = True) -> dict:

        from apps.data_access.models import DrugInteraction

        stats = {"interactions_processed": 0, "chunks_created": 0, "errors": 0}

        collection = self.get_collection("drug_interactions")

        logger.info("Loading interactions into vector store...")

        interactions = DrugInteraction.objects.select_related("drug_a", "drug_b").all()

        chunk_buffer = []
        buffer_limit = 100

        iterator = tqdm(interactions, desc="Vectorizing interactions") if show_progress else interactions

        for interaction in iterator:
            try:
                chunk_id = f"interaction_{interaction.drug_a.canonical_name}_{interaction.drug_b.canonical_name}"

                text = (
                    f"Drug interaction between {interaction.drug_a.canonical_name} "
                    f"and {interaction.drug_b.canonical_name}. "
                    f"Severity: {interaction.severity}. "
                    f"{interaction.description[:1500]}"
                )

                chunk_buffer.append({
                    "id": chunk_id,
                    "text": text,
                    "metadata": {
                        "drug_a": interaction.drug_a.canonical_name,
                        "drug_b": interaction.drug_b.canonical_name,
                        "severity": interaction.severity,
                        "source": interaction.source,
                    },
                })

                if len(chunk_buffer) >= buffer_limit:
                    self._insert_chunks(collection, chunk_buffer)
                    stats["chunks_created"] += len(chunk_buffer)
                    chunk_buffer = []

                stats["interactions_processed"] += 1

            except Exception as e:
                logger.error(f"Error processing interaction: {e}")
                stats["errors"] += 1

        # Insert remaining
        if chunk_buffer:
            self._insert_chunks(collection, chunk_buffer)
            stats["chunks_created"] += len(chunk_buffer)

        logger.info(f"Interactions loaded: {stats}")
        return stats

    def load_adverse_reactions(self, show_progress: bool = True) -> dict:

        from apps.data_access.models import DrugAdverseReaction

        stats = {"reactions_processed": 0, "chunks_created": 0, "errors": 0}

        collection = self.get_collection("adverse_reactions")

        logger.info("Loading adverse reactions into vector store...")

        # Group reactions by drug
        reactions = (
            DrugAdverseReaction.objects
            .select_related("drug", "reaction")
            .order_by("drug__canonical_name")
        )

        chunk_buffer = []
        buffer_limit = 100

        iterator = tqdm(reactions, desc="Vectorizing reactions") if show_progress else reactions

        for drug_reaction in iterator:
            try:
                chunk_id = f"reaction_{drug_reaction.drug.canonical_name}_{drug_reaction.reaction.preferred_term_normalized}"

                text = (
                    f"{drug_reaction.drug.canonical_name} may cause "
                    f"{drug_reaction.reaction.preferred_term}. "
                )
                if drug_reaction.frequency:
                    text += f"Frequency: {drug_reaction.frequency}. "
                if drug_reaction.source_text:
                    text += drug_reaction.source_text[:500]

                chunk_buffer.append({
                    "id": chunk_id,
                    "text": text,
                    "metadata": {
                        "drug": drug_reaction.drug.canonical_name,
                        "reaction": drug_reaction.reaction.preferred_term,
                        "source": drug_reaction.source,
                    },
                })

                if len(chunk_buffer) >= buffer_limit:
                    self._insert_chunks(collection, chunk_buffer)
                    stats["chunks_created"] += len(chunk_buffer)
                    chunk_buffer = []

                stats["reactions_processed"] += 1

            except Exception as e:
                logger.error(f"Error processing reaction: {e}")
                stats["errors"] += 1

        # Insert remaining
        if chunk_buffer:
            self._insert_chunks(collection, chunk_buffer)
            stats["chunks_created"] += len(chunk_buffer)

        logger.info(f"Adverse reactions loaded: {stats}")
        return stats

    def load_all(self, show_progress: bool = True) -> dict:

        all_stats = {}

        all_stats["drug_labels"] = self.load_drug_labels(show_progress)
        all_stats["interactions"] = self.load_interactions(show_progress)
        all_stats["adverse_reactions"] = self.load_adverse_reactions(show_progress)

        return all_stats
