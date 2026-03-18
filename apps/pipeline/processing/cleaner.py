"""
Data Cleaner - Handle nulls, duplicates, and standardize text fields.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class CleaningStats:
    """Statistics from data cleaning operations."""

    total_records: int = 0
    null_values_found: int = 0
    duplicates_removed: int = 0
    invalid_records: int = 0
    cleaned_records: int = 0


class DataCleaner:
    """
    Cleans and standardizes data from various sources.
    """

    # Common null representations
    NULL_VALUES = {
        "",
        "null",
        "none",
        "n/a",
        "na",
        "nan",
        "-",
        ".",
        "unknown",
        "not available",
        "not specified",
    }

    def __init__(self):
        self.stats = CleaningStats()

    def reset_stats(self):
        """Reset cleaning statistics."""
        self.stats = CleaningStats()

    def is_null(self, value: Any) -> bool:
        """Check if a value represents null/missing data."""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in self.NULL_VALUES
        return False

    def clean_string(self, value: Any, lowercase: bool = True) -> Optional[str]:
        """
        Clean a string value.

        Args:
            value: Input value
            lowercase: Whether to convert to lowercase

        Returns:
            Cleaned string or None if null
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        result = str(value).strip()

        # Remove excessive whitespace
        result = " ".join(result.split())

        if lowercase:
            result = result.lower()

        return result if result else None

    def clean_text(self, value: Any) -> Optional[str]:
        """
        Clean a text field (preserve case, handle multiline).

        Args:
            value: Input value

        Returns:
            Cleaned text or None if null
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        result = str(value).strip()

        # Normalize line endings
        result = result.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive blank lines
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result if result else None

    def clean_integer(self, value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Optional[int]:
        """
        Clean and validate an integer value.

        Args:
            value: Input value
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)

        Returns:
            Cleaned integer or None if invalid
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        try:
            # Handle string representations
            if isinstance(value, str):
                # Remove common suffixes
                value = re.sub(r"[^\d.-]", "", value)

            result = int(float(value))

            # Validate range
            if min_val is not None and result < min_val:
                self.stats.invalid_records += 1
                return None
            if max_val is not None and result > max_val:
                self.stats.invalid_records += 1
                return None

            return result
        except (ValueError, TypeError):
            self.stats.invalid_records += 1
            return None

    def clean_float(self, value: Any, min_val: Optional[float] = None, max_val: Optional[float] = None) -> Optional[float]:
        """
        Clean and validate a float value.
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        try:
            if isinstance(value, str):
                value = re.sub(r"[^\d.-]", "", value)

            result = float(value)

            if min_val is not None and result < min_val:
                self.stats.invalid_records += 1
                return None
            if max_val is not None and result > max_val:
                self.stats.invalid_records += 1
                return None

            return result
        except (ValueError, TypeError):
            self.stats.invalid_records += 1
            return None

    def clean_date(self, value: Any, formats: Optional[list[str]] = None) -> Optional[datetime]:
        """
        Clean and parse a date value.

        Args:
            value: Input value
            formats: List of date formats to try

        Returns:
            Parsed datetime or None if invalid
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        if formats is None:
            formats = [
                "%Y%m%d",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ]

        value_str = str(value).strip()

        for fmt in formats:
            try:
                return datetime.strptime(value_str, fmt)
            except ValueError:
                continue

        self.stats.invalid_records += 1
        return None

    def clean_boolean(self, value: Any) -> Optional[bool]:
        """
        Clean and parse a boolean value.
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        if isinstance(value, bool):
            return value

        str_val = str(value).strip().lower()

        if str_val in ("1", "true", "yes", "y", "t"):
            return True
        if str_val in ("0", "false", "no", "n", "f", "2"):  # 2 often means "no" in FDA data
            return False

        self.stats.invalid_records += 1
        return None

    def clean_list_string(self, value: Any, separator: str = ";") -> list[str]:
        """
        Clean a string containing multiple values separated by a delimiter.

        Args:
            value: Input value (e.g., "item1; item2; item3")
            separator: Delimiter between items

        Returns:
            List of cleaned strings
        """
        if self.is_null(value):
            return []

        items = str(value).split(separator)
        cleaned = []

        for item in items:
            clean_item = self.clean_string(item, lowercase=False)
            if clean_item:
                cleaned.append(clean_item)

        return cleaned

    def deduplicate_list(self, items: list[Any], key_func=None) -> list[Any]:
        """
        Remove duplicates from a list while preserving order.

        Args:
            items: List of items
            key_func: Optional function to extract comparison key

        Returns:
            Deduplicated list
        """
        seen = set()
        result = []

        for item in items:
            key = key_func(item) if key_func else item
            if key not in seen:
                seen.add(key)
                result.append(item)
            else:
                self.stats.duplicates_removed += 1

        return result

    def clean_drug_name(self, value: Any) -> Optional[str]:
        """
        Special cleaning for drug names.
        Handles patterns like "DRUG-100", "DRUG (strength)", etc.
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        name = str(value).strip()

        # Remove dosage suffixes (e.g., "-100", "-500")
        name = re.sub(r"-\d+$", "", name)

        # Remove parenthetical dosage info
        name = re.sub(r"\s*\([^)]*\)", "", name)

        # Remove "HCI", "hydrochloride" etc. for matching
        # (but keep original for display)
        # name = re.sub(r'\s+(hcl|hydrochloride|sodium|potassium|calcium|acetate)$', '', name, flags=re.IGNORECASE)

        # Normalize whitespace
        name = " ".join(name.split())

        return name if name else None

    def clean_reaction_name(self, value: Any) -> Optional[str]:
        """
        Special cleaning for adverse reaction names.
        """
        if self.is_null(value):
            self.stats.null_values_found += 1
            return None

        name = str(value).strip()

        # Normalize case (title case for display)
        name = name.lower()

        # Normalize whitespace
        name = " ".join(name.split())

        return name if name else None


# Global singleton
_cleaner: Optional[DataCleaner] = None


def get_cleaner() -> DataCleaner:
    """Get the global DataCleaner instance."""
    global _cleaner
    if _cleaner is None:
        _cleaner = DataCleaner()
    return _cleaner
