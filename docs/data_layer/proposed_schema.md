# MedGuard AI - Proposed Schema Design

## Overview

This document proposes the database schema for MedGuard AI, split between:
- **MySQL**: Structured relational data (drugs, reactions, interactions)
- **ChromaDB**: Vector embeddings for semantic search (drug labels, warnings)

---

## A. MySQL Schema (Django Models)

### A.1 Core Drug Entity

```python
# data_access/models/drug.py

from django.db import models


class Drug(models.Model):
    """
    Central drug entity - the normalized reference for all drug names.
    Links brand names, generics, and identifiers to a single canonical drug.
    """
    id = models.BigAutoField(primary_key=True)

    # Canonical name (lowercase, standardized)
    canonical_name = models.CharField(max_length=500, unique=True, db_index=True)

    # External identifiers (nullable - not all drugs have all IDs)
    rxcui = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    pubchem_cid = models.CharField(max_length=50, null=True, blank=True)

    # Metadata
    is_combination = models.BooleanField(default=False)  # Multi-drug combination
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drugs'
        indexes = [
            models.Index(fields=['canonical_name']),
            models.Index(fields=['rxcui']),
        ]

    def __str__(self):
        return self.canonical_name


class DrugAlias(models.Model):
    """
    All known names for a drug (brand names, generic variations, spelling variants).
    Enables fuzzy matching: search by alias -> get canonical drug.
    """
    id = models.BigAutoField(primary_key=True)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='aliases')

    alias = models.CharField(max_length=500, db_index=True)
    alias_type = models.CharField(max_length=20, choices=[
        ('brand', 'Brand Name'),
        ('generic', 'Generic Name'),
        ('variant', 'Spelling Variant'),
        ('combination', 'Combination Product'),
    ])

    # Normalized lowercase for case-insensitive lookup
    alias_normalized = models.CharField(max_length=500, db_index=True)

    class Meta:
        db_table = 'drug_aliases'
        unique_together = ['drug', 'alias_normalized']
        indexes = [
            models.Index(fields=['alias_normalized']),
            models.Index(fields=['alias_type']),
        ]
```

### A.2 Indications (What Drug Treats)

```python
# data_access/models/indication.py

from django.db import models
from .drug import Drug


class Indication(models.Model):
    """
    Medical conditions/symptoms that a drug is indicated for.
    Extracted from drug labels 'indications_and_usage' field.
    """
    id = models.BigAutoField(primary_key=True)

    name = models.CharField(max_length=500, unique=True, db_index=True)
    name_normalized = models.CharField(max_length=500, db_index=True)

    # MedDRA code if available
    meddra_code = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'indications'
        indexes = [
            models.Index(fields=['name_normalized']),
        ]


class DrugIndication(models.Model):
    """
    Many-to-many relationship: which drugs treat which conditions.
    """
    id = models.BigAutoField(primary_key=True)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='indications')
    indication = models.ForeignKey(Indication, on_delete=models.CASCADE, related_name='drugs')

    # Source tracking
    source = models.CharField(max_length=50)  # 'fda_label', 'sider', etc.
    confidence = models.FloatField(default=1.0)  # 0.0-1.0 confidence score

    class Meta:
        db_table = 'drug_indications'
        unique_together = ['drug', 'indication']
```

### A.3 Adverse Reactions (Side Effects)

```python
# data_access/models/adverse_reaction.py

from django.db import models
from .drug import Drug


class AdverseReaction(models.Model):
    """
    Known adverse reactions / side effects.
    Uses MedDRA Preferred Terms when available.
    """
    id = models.BigAutoField(primary_key=True)

    # MedDRA Preferred Term
    preferred_term = models.CharField(max_length=500, unique=True, db_index=True)
    preferred_term_normalized = models.CharField(max_length=500, db_index=True)

    # MedDRA code
    meddra_code = models.CharField(max_length=20, null=True, blank=True, db_index=True)

    # Severity classification
    severity_category = models.CharField(max_length=20, null=True, choices=[
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('life_threatening', 'Life-Threatening'),
    ])

    class Meta:
        db_table = 'adverse_reactions'
        indexes = [
            models.Index(fields=['preferred_term_normalized']),
            models.Index(fields=['meddra_code']),
        ]


class DrugAdverseReaction(models.Model):
    """
    Links drugs to their known adverse reactions with frequency data.
    """
    id = models.BigAutoField(primary_key=True)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='adverse_reactions')
    reaction = models.ForeignKey(AdverseReaction, on_delete=models.CASCADE, related_name='drugs')

    # Frequency of occurrence (from label or computed from events)
    frequency = models.CharField(max_length=20, null=True, choices=[
        ('very_common', '>10%'),
        ('common', '1-10%'),
        ('uncommon', '0.1-1%'),
        ('rare', '0.01-0.1%'),
        ('very_rare', '<0.01%'),
        ('unknown', 'Unknown'),
    ])

    # Report count from adverse event data
    report_count = models.IntegerField(default=0)

    # Source
    source = models.CharField(max_length=50)

    class Meta:
        db_table = 'drug_adverse_reactions'
        unique_together = ['drug', 'reaction']
        indexes = [
            models.Index(fields=['report_count']),
        ]
```

### A.4 Drug Interactions (CRITICAL)

```python
# data_access/models/interaction.py

from django.db import models
from .drug import Drug


class DrugInteraction(models.Model):
    """
    Drug-drug interactions. This is the CORE table for risk assessment.

    Interaction between drug_a and drug_b (order doesn't matter,
    but we store drug_a.id < drug_b.id to avoid duplicates).
    """
    id = models.BigAutoField(primary_key=True)

    drug_a = models.ForeignKey(
        Drug, on_delete=models.CASCADE,
        related_name='interactions_as_a'
    )
    drug_b = models.ForeignKey(
        Drug, on_delete=models.CASCADE,
        related_name='interactions_as_b'
    )

    # Severity
    severity = models.CharField(max_length=20, choices=[
        ('contraindicated', 'Contraindicated - Do Not Use Together'),
        ('major', 'Major - Serious Consequences Likely'),
        ('moderate', 'Moderate - Use With Caution'),
        ('minor', 'Minor - Minimal Clinical Significance'),
        ('unknown', 'Unknown Severity'),
    ], db_index=True)

    # Description of what happens
    description = models.TextField()

    # Clinical effect
    clinical_effect = models.TextField(null=True, blank=True)

    # Recommendation
    management = models.TextField(null=True, blank=True)

    # Evidence level
    evidence_level = models.CharField(max_length=20, null=True, choices=[
        ('established', 'Established'),
        ('probable', 'Probable'),
        ('suspected', 'Suspected'),
        ('theoretical', 'Theoretical'),
    ])

    # Source tracking
    source = models.CharField(max_length=50)
    source_label_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'drug_interactions'
        unique_together = ['drug_a', 'drug_b']
        indexes = [
            models.Index(fields=['drug_a', 'severity']),
            models.Index(fields=['drug_b', 'severity']),
            models.Index(fields=['severity']),
        ]

    def save(self, *args, **kwargs):
        # Ensure drug_a.id < drug_b.id to prevent duplicate pairs
        if self.drug_a_id > self.drug_b_id:
            self.drug_a_id, self.drug_b_id = self.drug_b_id, self.drug_a_id
        super().save(*args, **kwargs)
```

### A.5 Contraindications

```python
# data_access/models/contraindication.py

from django.db import models
from .drug import Drug


class Contraindication(models.Model):
    """
    Conditions/situations where a drug should NOT be used.
    Extracted from drug labels 'contraindications' field.
    """
    id = models.BigAutoField(primary_key=True)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='contraindications')

    # What the contraindication is
    condition = models.TextField()
    condition_normalized = models.CharField(max_length=500, db_index=True)

    # Severity
    severity = models.CharField(max_length=20, choices=[
        ('absolute', 'Absolute - Never Use'),
        ('relative', 'Relative - Use With Extreme Caution'),
    ], default='absolute')

    # Source
    source = models.CharField(max_length=50)
    source_label_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'contraindications'
        indexes = [
            models.Index(fields=['condition_normalized']),
        ]
```

### A.6 Adverse Event Reports (for frequency analysis)

```python
# data_access/models/event_report.py

from django.db import models
from .drug import Drug
from .adverse_reaction import AdverseReaction


class AdverseEventReport(models.Model):
    """
    Individual adverse event reports from FAERS/FDA data.
    Used for computing reaction frequencies and detecting patterns.
    """
    id = models.BigAutoField(primary_key=True)

    # External report ID
    safety_report_id = models.CharField(max_length=50, unique=True, db_index=True)

    # Report metadata
    report_date = models.DateField(null=True)
    is_serious = models.BooleanField(default=False)
    seriousness_death = models.BooleanField(default=False)
    seriousness_hospitalization = models.BooleanField(default=False)

    # Patient demographics (optional)
    patient_age = models.IntegerField(null=True)
    patient_sex = models.CharField(max_length=1, null=True)  # M/F/U

    # Source file for traceability
    source = models.CharField(max_length=50)
    source_file = models.CharField(max_length=200, null=True)

    class Meta:
        db_table = 'adverse_event_reports'
        indexes = [
            models.Index(fields=['report_date']),
            models.Index(fields=['is_serious']),
        ]


class EventReportDrug(models.Model):
    """
    Drugs involved in an adverse event report.
    """
    id = models.BigAutoField(primary_key=True)
    report = models.ForeignKey(AdverseEventReport, on_delete=models.CASCADE, related_name='drugs')
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE)

    # Role of drug in the event
    characterization = models.CharField(max_length=20, choices=[
        ('suspect', 'Primary Suspect'),
        ('concomitant', 'Concomitant'),
        ('interacting', 'Interacting'),
    ])

    # Dosage info if available
    dosage = models.CharField(max_length=100, null=True)
    indication = models.CharField(max_length=500, null=True)

    class Meta:
        db_table = 'event_report_drugs'
        indexes = [
            models.Index(fields=['drug', 'characterization']),
        ]


class EventReportReaction(models.Model):
    """
    Reactions reported in an adverse event.
    """
    id = models.BigAutoField(primary_key=True)
    report = models.ForeignKey(AdverseEventReport, on_delete=models.CASCADE, related_name='reactions')
    reaction = models.ForeignKey(AdverseReaction, on_delete=models.CASCADE)

    # Outcome if known
    outcome = models.CharField(max_length=20, null=True, choices=[
        ('recovered', 'Recovered'),
        ('recovering', 'Recovering'),
        ('not_recovered', 'Not Recovered'),
        ('fatal', 'Fatal'),
        ('unknown', 'Unknown'),
    ])

    class Meta:
        db_table = 'event_report_reactions'
```

### A.7 MedDRA Terminology Lookup

```python
# data_access/models/meddra.py

from django.db import models


class MedDRACode(models.Model):
    """
    MedDRA code to preferred term mapping.
    Needed to decode ADR codes in synthetic data.
    """
    code = models.CharField(max_length=20, primary_key=True)
    preferred_term = models.CharField(max_length=500, db_index=True)

    # Hierarchy
    soc_code = models.CharField(max_length=20, null=True)  # System Organ Class
    soc_name = models.CharField(max_length=200, null=True)

    class Meta:
        db_table = 'meddra_codes'
```

---

## A.8 Complete ER Diagram

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│      Drug       │      │   DrugAlias      │      │   Indication    │
├─────────────────┤      ├──────────────────┤      ├─────────────────┤
│ id (PK)         │◄─────│ drug_id (FK)     │      │ id (PK)         │
│ canonical_name  │      │ alias            │      │ name            │
│ rxcui           │      │ alias_type       │      │ meddra_code     │
│ pubchem_cid     │      │ alias_normalized │      └────────┬────────┘
│ is_combination  │      └──────────────────┘               │
└───────┬─────────┘                                         │
        │                                     ┌─────────────┴─────────────┐
        │                                     │      DrugIndication       │
        │                                     ├───────────────────────────┤
        ├─────────────────────────────────────│ drug_id (FK)              │
        │                                     │ indication_id (FK)        │
        │                                     │ source, confidence        │
        │                                     └───────────────────────────┘
        │
        │      ┌───────────────────┐      ┌────────────────────────┐
        │      │  AdverseReaction  │      │  DrugAdverseReaction   │
        │      ├───────────────────┤      ├────────────────────────┤
        │      │ id (PK)           │◄─────│ reaction_id (FK)       │
        │      │ preferred_term    │      │ drug_id (FK)           │◄─────┐
        │      │ meddra_code       │      │ frequency              │      │
        │      │ severity_category │      │ report_count           │      │
        │      └───────────────────┘      └────────────────────────┘      │
        │                                                                  │
        │      ┌──────────────────────┐                                   │
        ├─────►│   DrugInteraction    │◄──────────────────────────────────┤
        │      ├──────────────────────┤                                   │
        │      │ id (PK)              │                                   │
        │      │ drug_a_id (FK)       │                                   │
        │      │ drug_b_id (FK)       │                                   │
        │      │ severity             │                                   │
        │      │ description          │                                   │
        │      │ clinical_effect      │                                   │
        │      │ management           │                                   │
        │      └──────────────────────┘                                   │
        │                                                                  │
        │      ┌──────────────────────┐                                   │
        └─────►│  Contraindication    │                                   │
               ├──────────────────────┤                                   │
               │ id (PK)              │                                   │
               │ drug_id (FK)         │                                   │
               │ condition            │                                   │
               │ severity             │                                   │
               └──────────────────────┘                                   │
                                                                          │
        ┌──────────────────────────┐      ┌────────────────────────┐     │
        │   AdverseEventReport     │      │   EventReportDrug      │     │
        ├──────────────────────────┤      ├────────────────────────┤     │
        │ id (PK)                  │◄─────│ report_id (FK)         │     │
        │ safety_report_id         │      │ drug_id (FK)           │─────┘
        │ is_serious               │      │ characterization       │
        │ seriousness_death        │      └────────────────────────┘
        │ patient_age, patient_sex │
        └──────────────────────────┘      ┌────────────────────────┐
                     │                    │  EventReportReaction   │
                     └───────────────────►├────────────────────────┤
                                          │ report_id (FK)         │
                                          │ reaction_id (FK)       │
                                          │ outcome                │
                                          └────────────────────────┘
```

---

## A.9 Indexing Strategy

### Primary Indexes (Required)

| Table | Index | Purpose |
|-------|-------|---------|
| drugs | canonical_name | Drug name lookups |
| drugs | rxcui | Cross-reference lookups |
| drug_aliases | alias_normalized | Fuzzy drug name matching |
| drug_interactions | (drug_a, drug_b) | Interaction checks |
| drug_interactions | severity | Filter by severity |
| drug_adverse_reactions | (drug_id) | Get drug's side effects |
| adverse_event_reports | safety_report_id | Deduplication |

### Composite Indexes (Performance)

```sql
-- Fast interaction lookup for a single drug
CREATE INDEX idx_interactions_drug_a ON drug_interactions(drug_a_id, severity);
CREATE INDEX idx_interactions_drug_b ON drug_interactions(drug_b_id, severity);

-- Fast adverse reaction lookup with frequency
CREATE INDEX idx_drug_reactions_count ON drug_adverse_reactions(drug_id, report_count DESC);

-- Event report analysis
CREATE INDEX idx_event_reports_serious ON adverse_event_reports(is_serious, report_date);
```

### Full-Text Search (MySQL)

```sql
-- Enable full-text search on interaction descriptions
ALTER TABLE drug_interactions ADD FULLTEXT INDEX ft_interaction_desc (description, clinical_effect);

-- Enable full-text on contraindications
ALTER TABLE contraindications ADD FULLTEXT INDEX ft_contraindication (condition);
```

---

## B. Vector Store Strategy (ChromaDB)

### B.1 Collection Design

```python
# Three separate collections for different retrieval needs

COLLECTIONS = {
    # 1. Drug label sections - for answering "Is this drug safe for X?"
    "drug_labels": {
        "description": "Full drug label sections (indications, warnings, interactions)",
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "distance_metric": "cosine",
    },

    # 2. Interaction descriptions - for answering "What happens if I take A with B?"
    "drug_interactions": {
        "description": "Drug interaction text chunks",
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "distance_metric": "cosine",
    },

    # 3. Adverse reactions - for answering "What side effects should I expect?"
    "adverse_reactions": {
        "description": "Side effect descriptions and frequencies",
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "distance_metric": "cosine",
    },
}
```

### B.2 Chunking Strategy

#### Drug Labels Collection

**Source:** OpenFDA Drug Labels (drug-label/*.json)

**Chunking approach:**
```python
def chunk_drug_label(label: dict) -> list[dict]:
    """
    Split a drug label into meaningful chunks.
    Each section becomes 1+ chunks depending on length.
    """
    chunks = []

    # Sections to embed (ordered by importance)
    sections = [
        ('drug_interactions', 'Drug Interactions'),
        ('contraindications', 'Contraindications'),
        ('warnings_and_cautions', 'Warnings and Precautions'),
        ('boxed_warning', 'Boxed Warning'),
        ('adverse_reactions', 'Adverse Reactions'),
        ('indications_and_usage', 'Indications and Usage'),
        ('overdosage', 'Overdosage'),
    ]

    drug_names = label.get('openfda', {}).get('brand_name', [])
    generic_names = label.get('openfda', {}).get('generic_name', [])

    for field, section_name in sections:
        if field in label and label[field]:
            text = label[field][0]  # First element of list

            # Split long sections into ~500 token chunks
            section_chunks = split_into_chunks(text, max_tokens=500, overlap=50)

            for i, chunk_text in enumerate(section_chunks):
                chunks.append({
                    'id': f"{label['id']}_{field}_{i}",
                    'text': chunk_text,
                    'metadata': {
                        'label_id': label['id'],
                        'section': section_name,
                        'brand_names': drug_names[:5],  # Limit to first 5
                        'generic_names': generic_names[:5],
                        'chunk_index': i,
                        'source': 'fda_label',
                    }
                })

    return chunks
```

**Expected chunk count:** ~1.5-2 million chunks (260K labels × 5-8 sections average)

#### Drug Interactions Collection

**Source:** Drug Labels + OpenFDA Events (drugcharacterization=3)

**Chunking approach:**
```python
def chunk_interaction(drug_a: str, drug_b: str, description: str) -> dict:
    """
    Create a single chunk for each drug-drug interaction.
    Keep interaction description as atomic unit.
    """
    return {
        'id': f"interaction_{drug_a}_{drug_b}",
        'text': f"Drug interaction between {drug_a} and {drug_b}: {description}",
        'metadata': {
            'drug_a': drug_a.lower(),
            'drug_b': drug_b.lower(),
            'source': 'fda_label',
            'type': 'drug_interaction',
        }
    }
```

#### Adverse Reactions Collection

**Source:** Drug Labels (adverse_reactions section) + SIDER + Event aggregates

**Chunking approach:**
```python
def chunk_adverse_reaction(drug: str, reaction: str, frequency: str, context: str) -> dict:
    """
    Create searchable chunks for side effect queries.
    """
    text = f"{drug} may cause {reaction}. "
    if frequency:
        text += f"This occurs in approximately {frequency} of patients. "
    if context:
        text += context

    return {
        'id': f"reaction_{drug}_{reaction}",
        'text': text,
        'metadata': {
            'drug': drug.lower(),
            'reaction': reaction.lower(),
            'frequency': frequency,
            'source': 'composite',
        }
    }
```

### B.3 Metadata Schema

All chunks will have these standard metadata fields:

```python
METADATA_SCHEMA = {
    # Required
    'source': str,          # 'fda_label', 'sider', 'faers', 'synthetic'
    'type': str,            # 'indication', 'interaction', 'warning', 'reaction'

    # Drug identification (at least one required)
    'drug_canonical': str,   # Normalized drug name
    'brand_names': list,     # Brand name variants
    'generic_names': list,   # Generic name variants
    'rxcui': str,           # RxNorm identifier (if available)

    # Optional context
    'section': str,         # Label section name
    'severity': str,        # For interactions/warnings
    'label_id': str,        # FDA label ID for traceability
    'chunk_index': int,     # Position in multi-chunk documents
}
```

### B.4 Embedding Model

**Model:** `BAAI/bge-base-en-v1.5`

**Rationale:**
- 768-dimensional embeddings (good balance of quality vs. speed)
- Strong performance on semantic similarity benchmarks
- Medical/pharma domain shows good results
- Open source, self-hosted (no API costs)

**Configuration:**
```python
EMBEDDING_CONFIG = {
    'model_name': 'BAAI/bge-base-en-v1.5',
    'max_length': 512,  # Max tokens per chunk
    'normalize_embeddings': True,
    'batch_size': 32,  # For GPU processing
}
```

### B.5 Query Strategy

```python
def search_drug_safety(query: str, drug_names: list[str]) -> list[dict]:
    """
    Multi-collection search for drug safety queries.

    1. Search drug_labels with drug name filter
    2. Search drug_interactions if multiple drugs
    3. Search adverse_reactions for side effect queries
    """
    results = []

    # Always search labels
    label_results = collections['drug_labels'].query(
        query_texts=[query],
        n_results=10,
        where={'drug_canonical': {'$in': drug_names}}
    )
    results.extend(label_results)

    # Search interactions if multiple drugs
    if len(drug_names) > 1:
        interaction_results = collections['drug_interactions'].query(
            query_texts=[query],
            n_results=5,
            where={
                '$or': [
                    {'drug_a': {'$in': drug_names}},
                    {'drug_b': {'$in': drug_names}}
                ]
            }
        )
        results.extend(interaction_results)

    return results
```

---

## C. Data Flow Summary

```
                                    ┌─────────────────────────┐
                                    │    Raw Data Sources     │
                                    │  (CSV, JSON in /data/)  │
                                    └───────────┬─────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │   ETL Pipeline        │
                                    │   (Phase 2 loaders)   │
                                    └───────────┬───────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
        │   MySQL (RDB)     │       │  ChromaDB (Vec)   │       │ Normalization     │
        │                   │       │                   │       │ Dictionary        │
        │ - Drug entities   │       │ - Label chunks    │       │                   │
        │ - Interactions    │       │ - Interaction     │       │ - Brand→Generic   │
        │ - Adverse events  │       │   descriptions    │       │ - Aliases         │
        │ - Contraindic.    │       │ - Reaction texts  │       │ - Spellings       │
        └─────────┬─────────┘       └─────────┬─────────┘       └─────────┬─────────┘
                  │                           │                           │
                  └───────────────────────────┼───────────────────────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │   Data Access     │
                                    │   Layer (API)     │
                                    └─────────┬─────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │  Business Logic   │
                                    │  (Risk Engine)    │
                                    └───────────────────┘
```

---

## D. Estimated Record Counts

| Table | Expected Records | Storage Estimate |
|-------|------------------|------------------|
| drugs | ~100,000 | 10 MB |
| drug_aliases | ~500,000 | 50 MB |
| indications | ~10,000 | 2 MB |
| drug_indications | ~300,000 | 30 MB |
| adverse_reactions | ~50,000 | 10 MB |
| drug_adverse_reactions | ~2,000,000 | 200 MB |
| drug_interactions | ~500,000 | 100 MB |
| contraindications | ~200,000 | 50 MB |
| adverse_event_reports | ~350,000 | 100 MB |
| event_report_drugs | ~1,000,000 | 100 MB |
| event_report_reactions | ~1,500,000 | 100 MB |
| **MySQL Total** | - | **~750 MB** |

| Collection | Expected Chunks | Storage Estimate |
|------------|-----------------|------------------|
| drug_labels | ~2,000,000 | 2 GB |
| drug_interactions | ~500,000 | 500 MB |
| adverse_reactions | ~500,000 | 500 MB |
| **ChromaDB Total** | - | **~3 GB** |
