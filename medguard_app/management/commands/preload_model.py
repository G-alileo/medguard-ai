import logging
import time
from django.core.management.base import BaseCommand, CommandError
from apps.data_access.vector_store import get_chroma_client

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pre-load the embedding model to improve response times'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reload even if model is already loaded',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Pre-loading embedding model...'))

        start_time = time.time()

        try:
            chroma_client = get_chroma_client()

            if options['force'] or chroma_client._embedding_model is None:
                self.stdout.write('Loading SentenceTransformer model...')

                _ = chroma_client.embedding_model

                test_embedding = chroma_client.embed_query("test query")

                elapsed = time.time() - start_time

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Embedding model loaded successfully in {elapsed:.2f}s'
                    )
                )
                self.stdout.write(f'Test embedding dimension: {len(test_embedding)}')

                try:
                    stats = chroma_client.get_collection_stats()
                    if stats:
                        self.stdout.write('\n Vector store collections:')
                        for name, info in stats.items():
                            count = info.get('count', 0)
                            status = '' if count > 0 else ''
                            self.stdout.write(f'  {status} {name}: {count:,} records')
                except Exception as e:
                    self.stdout.write(f'  Could not load collection stats: {e}')

            else:
                self.stdout.write(self.style.WARNING('Model already loaded, use --force to reload'))

        except Exception as e:
            logger.error(f"Error pre-loading model: {e}", exc_info=True)
            raise CommandError(f'Failed to pre-load embedding model: {e}')

        self.stdout.write('\n' + self.style.SUCCESS(' Model pre-loading complete!'))