"""
Management command to load all data from raw sources.

Usage:
    python manage.py load_data --all
    python manage.py load_data --mysql-only
    python manage.py load_data --vector-only
"""

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load data from raw sources into MySQL and ChromaDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Load all data (MySQL + Vector)",
        )
        parser.add_argument(
            "--mysql-only",
            action="store_true",
            help="Load only MySQL data",
        )
        parser.add_argument(
            "--vector-only",
            action="store_true",
            help="Load only vector data (requires MySQL data first)",
        )
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Disable progress bars",
        )
        parser.add_argument(
            "--skip-events",
            action="store_true",
            help="Skip loading event reports (faster for testing)",
        )

    def handle(self, *args, **options):
        start_time = time.time()

        load_mysql = options["all"] or options["mysql_only"]
        load_vector = options["all"] or options["vector_only"]
        show_progress = not options["no_progress"]
        skip_events = options["skip_events"]

        if not load_mysql and not load_vector:
            self.stdout.write(
                self.style.WARNING("No action specified. Use --all, --mysql-only, or --vector-only")
            )
            return

        all_stats = {}

        # Load MySQL data
        if load_mysql:
            self.stdout.write(self.style.NOTICE("\n" + "=" * 60))
            self.stdout.write(self.style.NOTICE("LOADING DATA INTO MYSQL"))
            self.stdout.write(self.style.NOTICE("=" * 60 + "\n"))

            mysql_stats = self._load_mysql(show_progress, skip_events)
            all_stats["mysql"] = mysql_stats

        # Load vector data
        if load_vector:
            self.stdout.write(self.style.NOTICE("\n" + "=" * 60))
            self.stdout.write(self.style.NOTICE("LOADING DATA INTO CHROMADB"))
            self.stdout.write(self.style.NOTICE("=" * 60 + "\n"))

            vector_stats = self._load_vectors(show_progress)
            all_stats["vector"] = vector_stats

        # Print summary
        elapsed = time.time() - start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("DATA LOADING COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"\nTotal time: {elapsed_str}")
        self.stdout.write("\nStatistics:")

        self._print_stats(all_stats)

    def _load_mysql(self, show_progress: bool, skip_events: bool) -> dict:
        """Load data into MySQL."""
        from pipeline.loaders import MySQLLoader

        loader = MySQLLoader()
        stats = {}

        # 1. Load drugs
        self.stdout.write("\n[1/5] Loading drugs from OpenFDA labels...")
        stats["drugs_from_labels"] = loader.load_drugs_from_labels(show_progress)

        self.stdout.write("\n[2/5] Loading drugs from SIDER...")
        stats["drugs_from_sider"] = loader.load_drugs_from_sider(show_progress)

        # 2. Load adverse reactions
        self.stdout.write("\n[3/5] Loading adverse reactions...")
        stats["reactions_from_labels"] = loader.load_adverse_reactions_from_labels(show_progress)
        stats["reactions_from_sider"] = loader.load_adverse_reactions_from_sider(show_progress)

        # 3. Load interactions
        self.stdout.write("\n[4/5] Loading drug interactions...")
        stats["interactions"] = loader.load_interactions_from_labels(show_progress)

        # 4. Load event reports (optional)
        if not skip_events:
            self.stdout.write("\n[5/5] Loading event reports...")
            stats["events_openfda"] = loader.load_event_reports("openfda", show_progress)
            stats["events_fda_csv"] = loader.load_event_reports("fda_csv", show_progress)
        else:
            self.stdout.write("\n[5/5] Skipping event reports (--skip-events)")
            stats["events_skipped"] = True

        return stats

    def _load_vectors(self, show_progress: bool) -> dict:
        """Load data into ChromaDB."""
        from pipeline.loaders import VectorLoader

        loader = VectorLoader()
        stats = {}

        self.stdout.write("\n[1/3] Vectorizing drug labels...")
        stats["drug_labels"] = loader.load_drug_labels(show_progress)

        self.stdout.write("\n[2/3] Vectorizing interactions...")
        stats["interactions"] = loader.load_interactions(show_progress)

        self.stdout.write("\n[3/3] Vectorizing adverse reactions...")
        stats["adverse_reactions"] = loader.load_adverse_reactions(show_progress)

        return stats

    def _print_stats(self, stats: dict, indent: int = 0):
        """Recursively print statistics."""
        prefix = "  " * indent

        for key, value in stats.items():
            if isinstance(value, dict):
                self.stdout.write(f"{prefix}{key}:")
                self._print_stats(value, indent + 1)
            else:
                self.stdout.write(f"{prefix}{key}: {value}")
