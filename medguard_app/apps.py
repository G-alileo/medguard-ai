"""
MedGuard App Configuration.
"""

from django.apps import AppConfig


class MedguardAppConfig(AppConfig):
    """Configuration for the MedGuard application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "medguard_app"
    verbose_name = "MedGuard Drug Safety Assessment"

    def ready(self):
        """Initialize app when Django starts."""
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv or 'collectstatic' in sys.argv:
            return

        self._preload_embedding_model()

    def _preload_embedding_model(self):
        """Pre-load the embedding model for better performance."""
        import logging
        import time

        logger = logging.getLogger(__name__)

        try:
            logger.info(" Pre-loading embedding model...")
            start_time = time.time()

            from apps.data_access.vector_store import get_chroma_client

            chroma_client = get_chroma_client()
            _ = chroma_client.embedding_model

            elapsed = time.time() - start_time
            logger.info(f" Embedding model pre-loaded successfully in {elapsed:.2f}s")

        except Exception as e:
            logger.warning(f" Could not pre-load embedding model: {e}")
            logger.info(" Model will be loaded on first request instead")
