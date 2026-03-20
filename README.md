# MedGuard AI

Drug safety assessment system analyzing interactions, side effects, contraindications, and treatment appropriateness.

## How It Works overview

**MedGuard transforms medical input into instant risk assessments through a 5-stage pipeline:**

1. **Input Normalization** - Standardizes symptom/drug names using fuzzy matching
2. **Multi-Source Data Retrieval**:
   - SQLite database: Drug indications, contraindications, interactions
   - ChromaDB vector store: FDA labels, clinical context (sentence-transformers embeddings)
3. **Validation Pipeline**:
   - `TreatmentValidator`: Confirms drug treats symptoms
   - `InteractionChecker`: Cross-references against existing medications
   - `SideEffectAnalyzer`: Detects overlap between side effects and symptoms
4. **Risk Scoring** (`RiskEngine`):
   - Treatment mismatch: +40pts
   - Contraindicated interactions: +50pts
   - Major/Moderate/Minor: +30/+15/+5pts
   - Side effect overlap: +0-30pts
   - **Thresholds**: 0-25 (LOW) | 26-60 (MEDIUM) | 61+ (HIGH)
5. **AI Explanation** - DeepSeek LLM generates contextual summary

**Output**: Risk score + level + findings + AI explanation + safer alternatives (if needed)

**Processing Time**: <2 seconds end-to-end

![MedGuard Home](docs/images/home1.png)

## Features

- Drug interaction detection (contraindicated, major, moderate, minor)
- Treatment validation for symptoms
- Side effect overlap analysis
- Alternative drug suggestions
- Semantic search with vector embeddings
- Drug name normalization (brand/generic)

## Quick Start

```bash
git clone <repo-url>
cd medguard_v1
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv sync
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Visit http://127.0.0.1:8000

## Architecture

**Evaluation Pipeline:**
1. Input normalization (drug/symptom names)
2. Drug validation (database lookup)
3. Treatment validation (drug treats symptoms?)
4. Interaction checking (drug × existing medications)
5. Side effect analysis (overlap with symptoms)
6. Risk calculation (scoring + level assignment)
7. AI explanation generation
8. Alternative suggestions (if high risk)

**Core Components:**

| Component | File | Purpose |
|-----------|------|---------|
| Decision Pipeline | `orchestrator/decision_pipeline.py` | Main orchestrator |
| Treatment Validator | `orchestrator/treatment_validator.py` | Drug-symptom validation |
| Interaction Checker | `orchestrator/interaction_checker.py` | Drug-drug interactions |
| Side Effect Analyzer | `orchestrator/side_effect_analyzer.py` | Side effect overlap |
| Risk Engine | `orchestrator/risk_engine.py` | Risk scoring |

## Risk Scoring

| Level | Score | Action |
|-------|-------|--------|
| LOW | 0-25 | Safe to use |
| MEDIUM | 26-60 | Use caution |
| HIGH | 61+ | Not recommended |

**Points:** Treatment mismatch (+40) • Contraindicated (+50) • Major (+30) • Moderate (+15) • Minor (+5) • Side effects (+0-30)

## Screenshots

![Home Interface](docs/images/home2.png)
![Evaluation Form](docs/images/form1.png)
![Form Input](docs/images/form2.png)
![Risk Assessment](docs/images/result1.png)
![Details](docs/images/result2.png)
![Warnings](docs/images/result3.png)
![Recommendations](docs/images/result4.png)

## Usage

**Web:** Enter symptoms → proposed drug → existing medications → get assessment


## Tech Stack

Django 6.0 • ChromaDB • Sentence Transformers • RapidFuzz • DeepSeek • SQLite/MySQL

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) - Guidelines for issues, features, pull requests
- [MANUAL_TEST_INPUTS.md](MANUAL_TEST_INPUTS.md) - Copy-paste test scenarios

## Disclaimer

Educational purposes only. Not a substitute for professional medical advice.

## License

MIT License - See [LICENSE](LICENSE)
