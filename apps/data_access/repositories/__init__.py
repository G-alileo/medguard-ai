"""
Data Access Repositories - Clean interfaces for data access.
"""

from .drug_repository import DrugRepository
from .interaction_repository import InteractionRepository

__all__ = [
    "DrugRepository",
    "InteractionRepository",
]
