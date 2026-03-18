# MedGuard AI - Drug Name Normalization Strategy

## Problem Statement

Users may input drug names in many forms:
- Brand name: "Tylenol", "Advil", "Lipitor"
- Generic name: "acetaminophen", "ibuprofen", "atorvastatin"
- Misspellings: "paracetamol", "ibuprofin", "atorvistatin"
- With dosage: "Tylenol 500mg", "Lipitor 20"
- Combinations: "Tylenol with Codeine", "acetaminophen/hydrocodone"

Our data uses inconsistent naming across sources:
- SIDER: lowercase generic (`fluoxetine`)
- ADR Synthetic: Title case generic (`Fluoxetine`)
- FDA CSV: UPPERCASE brand (`PROZAC`)
- OpenFDA: Mixed brand/generic with variations

**Goal:** Map any user input to a single canonical drug identifier.

---

## Normalization Architecture

```
    User Input                    Normalization Pipeline                  Output
┌──────────────┐    ┌───────────────────────────────────────────┐    ┌────────────┐
│ "tylenol"    │───►│ 1. Preprocess (lowercase, strip, clean)   │───►│ Drug ID    │
│ "TYLENOL"    │    │ 2. Exact Match (alias lookup)             │    │ canonical_ │
│ "Tylenol500" │    │ 3. Fuzzy Match (if exact fails)          │    │ name       │
│ "tylenl"     │    │ 4. Fallback (ask user or return None)    │    │ "acetamin- │
└──────────────┘    └───────────────────────────────────────────┘    │ ophen"     │
                                                                      └────────────┘
```

---

## 1. Normalization Dictionary Structure

### 1.1 Base Dictionary (from OpenFDA data)

The OpenFDA drug labels provide authoritative brand-to-generic mappings:

```python
# Example entries extracted from OpenFDA
DRUG_MAPPINGS = {
    # Canonical name -> all known aliases
    "acetaminophen": {
        "canonical": "acetaminophen",
        "rxcui": "161",
        "aliases": [
            {"name": "tylenol", "type": "brand"},
            {"name": "paracetamol", "type": "generic"},  # International name
            {"name": "apap", "type": "abbreviation"},
            {"name": "n-acetyl-p-aminophenol", "type": "chemical"},
            {"name": "tylenol extra strength", "type": "brand"},
            {"name": "tylenol pm", "type": "brand_combination"},
        ]
    },

    "ibuprofen": {
        "canonical": "ibuprofen",
        "rxcui": "5640",
        "aliases": [
            {"name": "advil", "type": "brand"},
            {"name": "motrin", "type": "brand"},
            {"name": "nuprin", "type": "brand"},
            {"name": "midol", "type": "brand"},
            {"name": "ibuprofen sodium", "type": "salt_form"},
        ]
    },

    "atorvastatin": {
        "canonical": "atorvastatin",
        "rxcui": "83367",
        "aliases": [
            {"name": "lipitor", "type": "brand"},
            {"name": "atorvastatin calcium", "type": "salt_form"},
            {"name": "atorvastatin calcium trihydrate", "type": "salt_form"},
        ]
    },
}
```

### 1.2 Inverted Index for Fast Lookup

```python
# Generated from DRUG_MAPPINGS for O(1) lookup
ALIAS_TO_CANONICAL = {
    # All forms normalized to lowercase
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "apap": "acetaminophen",
    "acetaminophen": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "ibuprofen": "ibuprofen",
    "lipitor": "atorvastatin",
    "atorvastatin": "atorvastatin",
    # ... ~50,000+ entries
}
```

---

## 2. Normalization Pipeline

### 2.1 Preprocessing

```python
import re


def preprocess_drug_name(raw_input: str) -> str:
    """
    Clean and normalize user input for matching.

    Examples:
        "Tylenol 500mg" -> "tylenol"
        "ADVIL  " -> "advil"
        "Lipitor (20mg)" -> "lipitor"
        "aspirin/codeine" -> "aspirin codeine"  # Handle combinations
    """
    if not raw_input:
        return ""

    name = raw_input.strip().lower()

    # Remove dosage patterns (numbers with optional units)
    name = re.sub(r'\d+\s*(mg|ml|mcg|g|iu|units?)\b', '', name, flags=re.IGNORECASE)

    # Remove common suffixes
    name = re.sub(r'\s+(tablets?|capsules?|pills?|solution|syrup|cream|gel)\b', '', name)

    # Remove parenthetical content
    name = re.sub(r'\([^)]*\)', '', name)

    # Replace separators with space
    name = re.sub(r'[/\\,;]', ' ', name)

    # Remove special characters, keep letters and spaces
    name = re.sub(r'[^a-z\s]', '', name)

    # Normalize whitespace
    name = ' '.join(name.split())

    return name.strip()
```

### 2.2 Exact Match (Primary)

```python
def exact_match(normalized_name: str, alias_index: dict) -> str | None:
    """
    Direct lookup in alias index.
    Returns canonical name or None.
    """
    return alias_index.get(normalized_name)
```

### 2.3 Fuzzy Match (Fallback)

```python
from rapidfuzz import fuzz, process


def fuzzy_match(
    normalized_name: str,
    alias_index: dict,
    threshold: float = 85.0,
    max_results: int = 3
) -> list[tuple[str, float]]:
    """
    Fuzzy matching for typos and minor variations.

    Returns list of (canonical_name, confidence_score) tuples.
    Only returns matches above threshold.
    """
    # Get all unique canonical names for matching
    all_aliases = list(alias_index.keys())

    # Use rapidfuzz for efficient fuzzy matching
    matches = process.extract(
        normalized_name,
        all_aliases,
        scorer=fuzz.WRatio,  # Weighted ratio handles partial matches well
        limit=max_results * 2,  # Get extra candidates
    )

    results = []
    seen_canonical = set()

    for alias, score, _ in matches:
        if score >= threshold:
            canonical = alias_index[alias]
            if canonical not in seen_canonical:
                seen_canonical.add(canonical)
                results.append((canonical, score))
                if len(results) >= max_results:
                    break

    return results
```

### 2.4 Complete Normalization Function

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizationResult:
    canonical_name: Optional[str]
    confidence: float  # 0.0-1.0
    match_type: str  # 'exact', 'fuzzy', 'none'
    original_input: str
    suggestions: list[tuple[str, float]] = None  # For fuzzy matches


def normalize_drug_name(
    user_input: str,
    alias_index: dict,
    fuzzy_threshold: float = 85.0
) -> NormalizationResult:
    """
    Main normalization entry point.

    Strategy:
    1. Preprocess input
    2. Try exact match
    3. If no exact match, try fuzzy match
    4. Return best result with confidence
    """
    original = user_input
    normalized = preprocess_drug_name(user_input)

    if not normalized:
        return NormalizationResult(
            canonical_name=None,
            confidence=0.0,
            match_type='none',
            original_input=original
        )

    # Try exact match first
    exact = exact_match(normalized, alias_index)
    if exact:
        return NormalizationResult(
            canonical_name=exact,
            confidence=1.0,
            match_type='exact',
            original_input=original
        )

    # Try fuzzy match
    fuzzy_results = fuzzy_match(normalized, alias_index, fuzzy_threshold)

    if fuzzy_results:
        best_match, best_score = fuzzy_results[0]
        return NormalizationResult(
            canonical_name=best_match,
            confidence=best_score / 100.0,  # Convert to 0-1 scale
            match_type='fuzzy',
            original_input=original,
            suggestions=fuzzy_results[1:] if len(fuzzy_results) > 1 else None
        )

    # No match found
    return NormalizationResult(
        canonical_name=None,
        confidence=0.0,
        match_type='none',
        original_input=original
    )
```

---

## 3. Building the Dictionary

### 3.1 Primary Source: OpenFDA Drug Labels

```python
def extract_drug_mappings_from_labels(label_data: list[dict]) -> dict:
    """
    Extract brand/generic mappings from OpenFDA drug labels.

    Each label contains openfda.brand_name[] and openfda.generic_name[]
    """
    mappings = {}

    for label in label_data:
        openfda = label.get('openfda', {})

        brand_names = openfda.get('brand_name', [])
        generic_names = openfda.get('generic_name', [])
        rxcui_list = openfda.get('rxcui', [])
        substance_names = openfda.get('substance_name', [])

        if not generic_names:
            continue

        # Use first generic name as canonical
        canonical = generic_names[0].lower().strip()

        if canonical not in mappings:
            mappings[canonical] = {
                'canonical': canonical,
                'rxcui': rxcui_list[0] if rxcui_list else None,
                'aliases': set(),
            }

        # Add all names as aliases
        for name in brand_names:
            mappings[canonical]['aliases'].add(
                (name.lower().strip(), 'brand')
            )

        for name in generic_names:
            mappings[canonical]['aliases'].add(
                (name.lower().strip(), 'generic')
            )

        for name in substance_names:
            mappings[canonical]['aliases'].add(
                (name.lower().strip(), 'substance')
            )

    return mappings
```

### 3.2 Secondary Sources

```python
def merge_sider_drugs(mappings: dict, sider_data: list[dict]) -> dict:
    """
    Add SIDER drug names to existing mappings.
    SIDER uses lowercase generic names.
    """
    for row in sider_data:
        name = row['drugname'].lower().strip()
        cid = row['drug_id']

        if name in mappings:
            # Drug exists, add CID
            if not mappings[name].get('pubchem_cid'):
                mappings[name]['pubchem_cid'] = cid
        else:
            # New drug
            mappings[name] = {
                'canonical': name,
                'pubchem_cid': cid,
                'aliases': {(name, 'generic')},
            }

    return mappings


def merge_adr_synthetic_drugs(mappings: dict, adr_data: list[dict]) -> dict:
    """
    Add ADR synthetic drug names (may add spelling variations).
    """
    for row in adr_data:
        name = row['DrugName'].lower().strip()

        # These are common drugs, should already exist
        if name not in mappings:
            # Might be a spelling variation, try fuzzy match
            fuzzy_results = fuzzy_match(name, build_alias_index(mappings), threshold=90)
            if fuzzy_results:
                # Add as alias to existing drug
                canonical = fuzzy_results[0][0]
                mappings[canonical]['aliases'].add((name, 'variant'))
            else:
                # Truly new drug
                mappings[name] = {
                    'canonical': name,
                    'aliases': {(name, 'generic')},
                }

    return mappings
```

### 3.3 Manual Override List

Some mappings need manual curation:

```python
MANUAL_OVERRIDES = {
    # International name variations
    "paracetamol": "acetaminophen",  # UK/EU name for Tylenol
    "salbutamol": "albuterol",  # UK name

    # Common misspellings
    "ibuprofin": "ibuprofen",
    "amoxicilin": "amoxicillin",
    "atorvistatin": "atorvastatin",
    "metforman": "metformin",

    # Historical brand names
    "motrin": "ibuprofen",
    "nuprin": "ibuprofen",  # Discontinued brand

    # Partial names
    "asprin": "aspirin",
    "tylenol": "acetaminophen",
}
```

---

## 4. Combination Drug Handling

### 4.1 Detecting Combinations

```python
COMBINATION_PATTERNS = [
    # Explicit combinations
    r"^(.+)\s+and\s+(.+)$",  # "aspirin and codeine"
    r"^(.+)\s*[/\\]\s*(.+)$",  # "aspirin/codeine", "aspirin\codeine"
    r"^(.+)\s+with\s+(.+)$",  # "tylenol with codeine"
    r"^(.+)\s*-\s*(.+)$",  # "aspirin-caffeine"
]


def parse_combination(name: str) -> list[str] | None:
    """
    Check if drug name is a combination product.
    Returns list of individual drug names or None.
    """
    for pattern in COMBINATION_PATTERNS:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            drugs = [g.strip() for g in match.groups() if g.strip()]
            if len(drugs) > 1:
                return drugs

    return None


def normalize_combination(
    user_input: str,
    alias_index: dict
) -> list[NormalizationResult]:
    """
    Normalize combination drug input.
    Returns list of normalization results for each component.
    """
    preprocessed = preprocess_drug_name(user_input)
    components = parse_combination(preprocessed)

    if not components:
        # Not a combination, normalize as single drug
        return [normalize_drug_name(user_input, alias_index)]

    # Normalize each component
    results = []
    for component in components:
        result = normalize_drug_name(component, alias_index)
        results.append(result)

    return results
```

### 4.2 Known Combination Products

```python
# Pre-defined combination mappings
COMBINATION_PRODUCTS = {
    "tylenol pm": ["acetaminophen", "diphenhydramine"],
    "advil pm": ["ibuprofen", "diphenhydramine"],
    "vicodin": ["hydrocodone", "acetaminophen"],
    "percocet": ["oxycodone", "acetaminophen"],
    "excedrin": ["acetaminophen", "aspirin", "caffeine"],
    "mucinex dm": ["dextromethorphan", "guaifenesin"],
}
```

---

## 5. Sample Dictionary Output

### 5.1 Sample JSON Format

```json
{
  "version": "1.0",
  "generated": "2026-03-18",
  "drug_count": 50000,
  "alias_count": 150000,
  "drugs": {
    "acetaminophen": {
      "canonical": "acetaminophen",
      "rxcui": "161",
      "pubchem_cid": "CID1983",
      "aliases": [
        {"name": "acetaminophen", "type": "generic"},
        {"name": "paracetamol", "type": "generic"},
        {"name": "tylenol", "type": "brand"},
        {"name": "tylenol extra strength", "type": "brand"},
        {"name": "apap", "type": "abbreviation"},
        {"name": "n-acetyl-p-aminophenol", "type": "chemical"}
      ],
      "is_combination": false
    },
    "ibuprofen": {
      "canonical": "ibuprofen",
      "rxcui": "5640",
      "pubchem_cid": "CID3672",
      "aliases": [
        {"name": "ibuprofen", "type": "generic"},
        {"name": "advil", "type": "brand"},
        {"name": "motrin", "type": "brand"},
        {"name": "nuprin", "type": "brand"}
      ],
      "is_combination": false
    },
    "hydrocodone and acetaminophen": {
      "canonical": "hydrocodone and acetaminophen",
      "rxcui": "857001",
      "aliases": [
        {"name": "vicodin", "type": "brand"},
        {"name": "lortab", "type": "brand"},
        {"name": "norco", "type": "brand"},
        {"name": "hydrocodone/acetaminophen", "type": "generic"}
      ],
      "components": ["hydrocodone", "acetaminophen"],
      "is_combination": true
    }
  },
  "alias_index": {
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "acetaminophen": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "ibuprofen": "ibuprofen",
    "vicodin": "hydrocodone and acetaminophen"
  }
}
```

### 5.2 Common Drug Examples

| User Input | Preprocessed | Canonical | Confidence |
|------------|--------------|-----------|------------|
| "Tylenol" | tylenol | acetaminophen | 1.0 (exact) |
| "TYLENOL 500MG" | tylenol | acetaminophen | 1.0 (exact) |
| "tylenl" | tylenl | acetaminophen | 0.92 (fuzzy) |
| "paracetamol" | paracetamol | acetaminophen | 1.0 (exact) |
| "Lipitor 20" | lipitor | atorvastatin | 1.0 (exact) |
| "atorvistatin" | atorvistatin | atorvastatin | 0.95 (fuzzy) |
| "Advil PM" | advil pm | ibuprofen + diphenhydramine | 1.0 (combination) |
| "aspirin/codeine" | aspirin codeine | [aspirin, codeine] | 1.0 (combination) |

---

## 6. Performance Considerations

### 6.1 Lookup Performance

| Operation | Time Complexity | Expected Speed |
|-----------|-----------------|----------------|
| Exact match | O(1) | < 1ms |
| Fuzzy match (rapidfuzz) | O(n) | < 50ms for 150k aliases |
| Combination parsing | O(1) | < 1ms |

### 6.2 Memory Requirements

| Component | Size |
|-----------|------|
| Alias index (150k entries) | ~20 MB |
| Full drug dictionary | ~50 MB |
| Fuzzy matching index | ~30 MB |
| **Total** | **~100 MB** |

### 6.3 Caching Strategy

```python
from functools import lru_cache

# Cache normalized results for repeated queries
@lru_cache(maxsize=10000)
def cached_normalize(user_input: str) -> NormalizationResult:
    return normalize_drug_name(user_input, ALIAS_INDEX)
```

---

## 7. Implementation Plan

### Phase 2 Tasks (Dictionary Building)

1. **Extract from OpenFDA Labels** (~2 hours processing)
   - Parse all drug-label JSON files
   - Build brand/generic mappings
   - Extract RxCUI identifiers

2. **Merge SIDER Data** (~10 minutes)
   - Add missing drugs from SIDER
   - Add PubChem CIDs

3. **Apply Manual Overrides** (~5 minutes)
   - Load curated override list
   - Merge with extracted mappings

4. **Generate Inverted Index** (~5 minutes)
   - Build alias_index for fast lookup
   - Serialize to JSON for loading

5. **Validate Coverage** (~20 minutes)
   - Test against ADR synthetic drug list (20 drugs)
   - Test against FDA CSV drug list (sample 100)
   - Calculate coverage percentage

### Expected Output Files

```
data/processed/
├── drug_dictionary.json      # Full drug mappings
├── alias_index.json          # Inverted lookup index
└── normalization_stats.json  # Coverage and quality metrics
```

---

## 8. Edge Cases and Limitations

### Known Limitations

1. **Very rare drugs** - May not be in OpenFDA, will require manual addition
2. **Brand names in other languages** - Not covered in initial build
3. **Herbal/supplement products** - Limited coverage in FDA data
4. **Identical generic names for different compounds** - Rare but possible

### Fallback Behavior

When normalization fails:
1. Return original input with confidence 0.0
2. Flag for manual review
3. Optionally ask user to confirm from suggestions

```python
def handle_failed_normalization(result: NormalizationResult) -> str:
    """
    UI can use this to prompt user for clarification.
    """
    if result.match_type == 'none':
        return f"Could not identify drug: '{result.original_input}'. Did you mean one of these?"
    elif result.match_type == 'fuzzy' and result.confidence < 0.9:
        return f"Did you mean '{result.canonical_name}'? (Confidence: {result.confidence:.0%})"
    return None
```
