# MedGuard AI - Phase 2 Implementation Plan

## Overview

Phase 2 transforms raw data into the structured MySQL database and ChromaDB vector store defined in the proposed schema.

**Estimated Duration:** 8-12 hours (development + processing time)
**Prerequisites:** Phase 1 complete, schema approved

---

## Directory Structure (After Phase 2)

```
medguard_v1/
├── data/
│   ├── raw/                          # Existing raw data (read-only)
│   │   ├── SIDER_DATASET_KAGGLE/
│   │   ├── Adverse Drug Reaction (ADR) Reporting/
│   │   ├── FDA Drug Adverse Event Reports/
│   │   ├── drug-events/
│   │   └── drug-label/
│   ├── processed/                    # NEW: Intermediate processing outputs
│   │   ├── drug_dictionary.json
│   │   ├── alias_index.json
│   │   └── processing_logs/
│   └── chromadb/                     # NEW: Vector store data
│       ├── drug_labels/
│       ├── drug_interactions/
│       └── adverse_reactions/
├── medguard/
│   └── settings.py                   # Updated with new settings
├── pipeline/                         # NEW: Django app for ETL
│   ├── __init__.py
│   ├── management/
│   │   └── commands/
│   │       ├── load_drug_dictionary.py
│   │       ├── load_drug_labels.py
│   │       ├── load_adverse_events.py
│   │       ├── load_sider.py
│   │       ├── load_adr_synthetic.py
│   │       ├── build_embeddings.py
│   │       └── validate_data.py
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── base_loader.py
│   │   ├── label_loader.py
│   │   ├── event_loader.py
│   │   └── csv_loader.py
│   └── normalizer/
│       ├── __init__.py
│       └── drug_normalizer.py
├── data_access/                      # NEW: Django app for data models
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── drug.py
│   │   ├── indication.py
│   │   ├── adverse_reaction.py
│   │   ├── interaction.py
│   │   ├── contraindication.py
│   │   ├── event_report.py
│   │   └── meddra.py
│   ├── repositories/                 # Data access layer
│   │   ├── __init__.py
│   │   ├── drug_repository.py
│   │   └── interaction_repository.py
│   └── vector_store/
│       ├── __init__.py
│       └── chroma_client.py
└── docs/
    └── data_layer/                   # Existing documentation
```

---

## Task Breakdown

### Step 1: Project Setup (30 minutes)

**Tasks:**
1. Create Django apps (`pipeline`, `data_access`)
2. Update settings.py with MySQL and ChromaDB config
3. Install required packages
4. Create directory structure

**Commands:**
```bash
# Create Django apps
cd c:/Users/Keem/Desktop/projects/medguard_v1
uv run python manage.py startapp pipeline
uv run python manage.py startapp data_access

# Install additional packages
uv add mysqlclient chromadb sentence-transformers rapidfuzz tqdm

# Create directories
mkdir -p data/processed/processing_logs
mkdir -p data/chromadb
mkdir -p pipeline/management/commands
mkdir -p pipeline/loaders
mkdir -p pipeline/normalizer
mkdir -p data_access/models
mkdir -p data_access/repositories
mkdir -p data_access/vector_store
```

**Success Criteria:**
- [ ] Django apps created and registered in INSTALLED_APPS
- [ ] All directories exist
- [ ] `uv run python manage.py check` passes

---

### Step 2: Database Models (1 hour)

**Tasks:**
1. Implement all models from proposed_schema.md
2. Run migrations to create MySQL tables
3. Verify table structure

**Files to Create:**
- `data_access/models/drug.py`
- `data_access/models/indication.py`
- `data_access/models/adverse_reaction.py`
- `data_access/models/interaction.py`
- `data_access/models/contraindication.py`
- `data_access/models/event_report.py`
- `data_access/models/meddra.py`
- `data_access/models/__init__.py`

**Commands:**
```bash
# Create and apply migrations
uv run python manage.py makemigrations data_access
uv run python manage.py migrate

# Verify tables (optional, requires MySQL CLI)
mysql -u $DB_USER -p $DB_NAME -e "SHOW TABLES;"
```

**Success Criteria:**
- [ ] All 11 tables created
- [ ] Indexes created as specified
- [ ] Foreign keys working (test with admin)

---

### Step 3: Build Normalization Dictionary (2 hours)

**Task:** Extract drug name mappings from OpenFDA labels

**File to Create:** `pipeline/management/commands/load_drug_dictionary.py`

**Logic:**
```python
# Pseudocode
def handle(self):
    mappings = {}

    # 1. Process all drug-label JSON files
    for json_file in glob('data/raw/drug-label/*.json'):
        with open(json_file) as f:
            data = json.load(f)

        for label in data['results']:
            extract_and_merge_drug_mappings(label, mappings)

    # 2. Add SIDER drugs
    merge_sider_data(mappings)

    # 3. Apply manual overrides
    apply_overrides(mappings)

    # 4. Build inverted index
    alias_index = build_alias_index(mappings)

    # 5. Save to JSON
    save_dictionary(mappings, 'data/processed/drug_dictionary.json')
    save_index(alias_index, 'data/processed/alias_index.json')

    # 6. Report stats
    print(f"Extracted {len(mappings)} drugs with {len(alias_index)} aliases")
```

**Command:**
```bash
uv run python manage.py load_drug_dictionary
```

**Expected Output:**
- `data/processed/drug_dictionary.json` (~50 MB)
- `data/processed/alias_index.json` (~20 MB)

**Success Criteria:**
- [ ] Dictionary contains 40,000+ drugs
- [ ] Alias index contains 100,000+ entries
- [ ] All 20 ADR synthetic drugs found (100% coverage)
- [ ] All 13 common drugs from inspection report found

---

### Step 4: Load Drug Reference Data (2 hours)

**Task:** Populate MySQL Drug and DrugAlias tables

**File to Create:** `pipeline/management/commands/load_drugs.py`

**Logic:**
```python
def handle(self):
    # Load dictionary
    with open('data/processed/drug_dictionary.json') as f:
        dictionary = json.load(f)

    # Batch insert drugs
    drugs_to_create = []
    for canonical, data in dictionary['drugs'].items():
        drugs_to_create.append(Drug(
            canonical_name=canonical,
            rxcui=data.get('rxcui'),
            pubchem_cid=data.get('pubchem_cid'),
            is_combination=data.get('is_combination', False)
        ))

    Drug.objects.bulk_create(drugs_to_create, batch_size=1000)

    # Create alias mappings
    # ...
```

**Command:**
```bash
uv run python manage.py load_drugs
```

**Success Criteria:**
- [ ] ~40,000 rows in `drugs` table
- [ ] ~100,000 rows in `drug_aliases` table
- [ ] Can lookup "tylenol" -> "acetaminophen"

---

### Step 5: Load Drug Labels into ChromaDB (3 hours)

**Task:** Chunk and embed drug label text for semantic search

**File to Create:** `pipeline/management/commands/build_embeddings.py`

**Processing Steps:**
1. Parse each drug-label JSON file
2. Extract sections (indications, warnings, interactions, etc.)
3. Chunk long sections (~500 tokens each)
4. Add metadata (drug names, section type, label ID)
5. Generate BGE embeddings
6. Insert into ChromaDB

**Memory Management:**
```python
# Process in batches to manage memory
BATCH_SIZE = 100  # Labels per batch
CHUNK_BUFFER = 1000  # Chunks before inserting

def process_labels():
    for json_file in tqdm(glob('data/raw/drug-label/*.json')):
        with open(json_file) as f:
            data = json.load(f)

        chunk_buffer = []
        for label in data['results']:
            chunks = chunk_label(label)
            chunk_buffer.extend(chunks)

            if len(chunk_buffer) >= CHUNK_BUFFER:
                embed_and_insert(chunk_buffer)
                chunk_buffer = []

        # Insert remaining
        if chunk_buffer:
            embed_and_insert(chunk_buffer)

        # Force garbage collection between files
        gc.collect()
```

**Command:**
```bash
uv run python manage.py build_embeddings --collection=drug_labels
```

**Expected Processing Time:** ~30-45 minutes (60K labels from 3 files, CPU mode)

**Success Criteria:**
- [ ] ChromaDB `drug_labels` collection created
- [ ] ~1.5 million chunks indexed
- [ ] Test query returns relevant results

---

### Step 6: Load Adverse Event Reports (2 hours)

**Task:** Load FAERS/FDA event data into MySQL

**Files to Create:**
- `pipeline/management/commands/load_adverse_events.py`
- `pipeline/loaders/event_loader.py`

**Data Sources:**
1. OpenFDA drug-events JSON (primary - ~336K reports)
2. FDA Adverse Events CSV (secondary - 10K reports)

**Logic:**
```python
def load_openfda_events():
    for json_file in glob('data/raw/drug-events/*.json'):
        with open(json_file) as f:
            data = json.load(f)

        for report in data['results']:
            # Skip if already loaded
            if AdverseEventReport.objects.filter(
                safety_report_id=report['safetyreportid']
            ).exists():
                continue

            # Create report
            event_report = create_event_report(report)

            # Link drugs (requires drug normalization)
            for drug_data in report['patient'].get('drug', []):
                drug_name = drug_data.get('medicinalproduct', '')
                canonical = normalize_drug_name(drug_name)
                if canonical:
                    link_drug_to_report(event_report, canonical, drug_data)

            # Link reactions
            for reaction_data in report['patient'].get('reaction', []):
                link_reaction_to_report(event_report, reaction_data)
```

**Commands:**
```bash
# Load OpenFDA events
uv run python manage.py load_adverse_events --source=openfda

# Load FDA CSV (backup source)
uv run python manage.py load_adverse_events --source=fda_csv
```

**Success Criteria:**
- [ ] ~340K rows in `adverse_event_reports`
- [ ] ~1M rows in `event_report_drugs`
- [ ] ~1.5M rows in `event_report_reactions`
- [ ] Can query events by drug name

---

### Step 7: Load SIDER Data (30 minutes)

**Task:** Load drug-side effect relationships from SIDER

**File to Create:** `pipeline/management/commands/load_sider.py`

**Logic:**
```python
def handle(self):
    with open('data/raw/SIDER_DATASET_KAGGLE/drug_df.csv') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Normalize drug name
            drug = get_or_create_drug(row['drugname'])

            # Get or create adverse reaction
            reaction = get_or_create_reaction(row['pt'])

            # Create link
            DrugAdverseReaction.objects.get_or_create(
                drug=drug,
                reaction=reaction,
                defaults={
                    'source': 'sider',
                    'report_count': 1,
                }
            )
```

**Command:**
```bash
uv run python manage.py load_sider
```

**Success Criteria:**
- [ ] 650 drug-reaction links created
- [ ] 79 unique drugs linked
- [ ] 258 unique reactions linked

---

### Step 8: Load ADR Synthetic Data (1 hour)

**Task:** Load synthetic ADR data (primarily for concomitant drug patterns)

**File to Create:** `pipeline/management/commands/load_adr_synthetic.py`

**Logic (sampling approach due to 1M rows):**
```python
def handle(self):
    # Sample 100K rows for concomitant drug analysis
    # Full 1M is excessive for this use case

    with open('data/raw/Adverse Drug Reaction.../synthetic_drug_data.csv') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if i >= 100000:  # Sample limit
                break

            # Extract concomitant drug pairs
            if row['ConcomitantDrugs']:
                primary = normalize_drug_name(row['DrugName'])
                concomitants = parse_concomitant_drugs(row['ConcomitantDrugs'])

                for conc in concomitants:
                    # Record co-occurrence (not necessarily interaction)
                    record_cooccurrence(primary, conc)
```

**Command:**
```bash
uv run python manage.py load_adr_synthetic --limit=100000
```

**Success Criteria:**
- [ ] Concomitant drug pairs extracted
- [ ] Data available for interaction pattern analysis

---

### Step 9: Extract & Load Drug Interactions (2 hours)

**Task:** Parse drug_interactions section from labels into MySQL

**File to Create:** `pipeline/management/commands/load_interactions.py`

**Logic:**
```python
def extract_interactions(label: dict) -> list[dict]:
    """
    Parse drug_interactions text to extract structured interactions.

    Example input:
    "Avoid concomitant use with aliskiren in patients with eGFR < 60.
     Potassium-sparing diuretics: May lead to increased serum potassium.
     NSAIDs: May lead to increased risk of renal impairment."

    Use NLP/regex patterns to extract:
    - Interacting drug
    - Effect description
    - Severity (from keywords like "avoid", "contraindicated")
    """
    interactions = []
    text = label.get('drug_interactions', [''])[0]

    if not text:
        return []

    # Extract the primary drug from this label
    primary_drug = get_canonical_from_label(label)

    # Pattern matching for interaction mentions
    patterns = [
        r"(?:avoid|contraindicated).+?with\s+(\w+)",
        r"(\w+):\s*(?:may|can|will).+?(?:increase|decrease|cause)",
        r"concomitant use (?:of|with)\s+(\w+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            normalized = normalize_drug_name(match)
            if normalized:
                interactions.append({
                    'drug_a': primary_drug,
                    'drug_b': normalized,
                    'description': extract_relevant_sentence(text, match),
                    'severity': infer_severity(text, match),
                })

    return interactions
```

**Command:**
```bash
uv run python manage.py load_interactions
```

**Expected Output:** ~200,000 drug interaction records

**Success Criteria:**
- [ ] Interactions table populated
- [ ] Common interaction pairs present (e.g., warfarin + aspirin)
- [ ] Can query interactions for any drug

---

### Step 10: Build Interaction Embeddings (1 hour)

**Task:** Create vector embeddings for interaction text

**Command:**
```bash
uv run python manage.py build_embeddings --collection=drug_interactions
```

**Success Criteria:**
- [ ] ChromaDB `drug_interactions` collection created
- [ ] ~500K interaction chunks indexed

---

### Step 11: Validation & Testing (1 hour)

**Task:** Verify data integrity and query performance

**File to Create:** `pipeline/management/commands/validate_data.py`

**Validation Checks:**
```python
def handle(self):
    errors = []

    # 1. Check drug coverage
    test_drugs = ['acetaminophen', 'ibuprofen', 'warfarin', 'metformin']
    for drug in test_drugs:
        if not Drug.objects.filter(canonical_name=drug).exists():
            errors.append(f"Missing drug: {drug}")

    # 2. Check interaction data
    warfarin = Drug.objects.get(canonical_name='warfarin')
    interactions = DrugInteraction.objects.filter(
        Q(drug_a=warfarin) | Q(drug_b=warfarin)
    ).count()
    if interactions < 10:
        errors.append(f"Warfarin has only {interactions} interactions (expected 10+)")

    # 3. Check vector store
    results = chroma_client.query(
        collection='drug_labels',
        query_text='diabetes treatment',
        n_results=5
    )
    if len(results) < 5:
        errors.append("Vector search returned fewer than expected results")

    # 4. Performance check
    start = time.time()
    Drug.objects.get(canonical_name='acetaminophen')
    if time.time() - start > 0.01:  # 10ms threshold
        errors.append("Drug lookup too slow")

    # Report
    if errors:
        for e in errors:
            self.stderr.write(self.style.ERROR(e))
        sys.exit(1)
    else:
        self.stdout.write(self.style.SUCCESS("All validation checks passed!"))
```

**Command:**
```bash
uv run python manage.py validate_data
```

**Success Criteria:**
- [ ] All test drugs found
- [ ] Known interactions present
- [ ] Vector search returns relevant results
- [ ] Query performance < 100ms

---

## Environment Variables Required

Add to `.env`:
```bash
# Database
DB_ENGINE=django.db.backends.mysql
DB_NAME=medguard
DB_USER=medguard_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=3306

# Vector Store
CHROMADB_PATH=./data/chromadb
CHROMADB_COLLECTION_PREFIX=medguard_

# Embedding Model
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DEVICE=cpu  # AMD GPU requires ROCm; default to CPU

# DeepSeek API (for Phase 3)
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Django
SECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## Full Execution Order

```bash
# Phase 2 Execution Script
#!/bin/bash
set -e  # Exit on error

echo "=== Step 1: Project Setup ==="
uv run python manage.py startapp pipeline
uv run python manage.py startapp data_access
uv add mysqlclient chromadb sentence-transformers rapidfuzz tqdm

echo "=== Step 2: Database Migrations ==="
uv run python manage.py makemigrations data_access
uv run python manage.py migrate

echo "=== Step 3: Build Drug Dictionary ==="
uv run python manage.py load_drug_dictionary

echo "=== Step 4: Load Drug Reference Data ==="
uv run python manage.py load_drugs

echo "=== Step 5: Build Label Embeddings ==="
uv run python manage.py build_embeddings --collection=drug_labels

echo "=== Step 6: Load Adverse Events ==="
uv run python manage.py load_adverse_events --source=openfda

echo "=== Step 7: Load SIDER Data ==="
uv run python manage.py load_sider

echo "=== Step 8: Load ADR Synthetic Data ==="
uv run python manage.py load_adr_synthetic --limit=100000

echo "=== Step 9: Load Drug Interactions ==="
uv run python manage.py load_interactions

echo "=== Step 10: Build Interaction Embeddings ==="
uv run python manage.py build_embeddings --collection=drug_interactions

echo "=== Step 11: Validate ==="
uv run python manage.py validate_data

echo "=== Phase 2 Complete! ==="
```

---

## Confirmed Decisions

Based on user input:

1. **Data Scope**: Work with current 3 JSON files per source (3 drug-events, 3 drug-labels). Add more files after MVP is running.

2. **MySQL Setup**: MySQL is installed. User will configure connection in `.env` file.

3. **GPU**: AMD GPU available. Note: PyTorch has limited AMD support (requires ROCm). Will default to CPU for embeddings unless ROCm is configured. CPU processing is slower but functional.

4. **MedDRA Codes**: Infer meanings from context in the data (no external dictionary).

5. **Data Retention**: Keep raw data after loading (do not archive/compress).

6. **CI/CD**: Management commands should be idempotent (safe to re-run).

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Out of memory during JSON processing | High | Batch processing, gc.collect() between files |
| Drug normalization failures | Medium | Log failures, manual review queue |
| ChromaDB performance issues | Medium | Tune batch sizes, consider persistence settings |
| Missing drug-drug interactions | High | Combine multiple sources, flag low-confidence extractions |
| Long processing time | Low | Add progress bars, resumable checkpoints |

---

## Post-Phase 2 Checklist

After completing Phase 2, verify:

- [ ] Can look up any drug by brand or generic name
- [ ] Can get interactions for drug pairs (e.g., warfarin + aspirin)
- [ ] Can search for "diabetes medications" and get relevant results
- [ ] Can get adverse reactions for any drug
- [ ] API response time < 500ms for typical queries
- [ ] All validation checks pass
