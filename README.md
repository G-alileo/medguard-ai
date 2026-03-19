# MedGuard AI

Drug safety assessment system analyzing interactions, side effects, and treatment appropriateness.

![MedGuard Home](docs/images/home1.png)

## Features

Drug interaction detection • Treatment validation • Side effect analysis • Alternative suggestions • Semantic search • Name normalization

## Screenshots

### Home & Form
![Home Interface](docs/images/home2.png)
![Evaluation Form](docs/images/form1.png)
![Form Input](docs/images/form2.png)

### Results
![Risk Assessment](docs/images/result1.png)
![Details](docs/images/result2.png)
![Warnings](docs/images/result3.png)
![Recommendations](docs/images/result4.png)

### How It Works
![Overview](docs/images/how_ti_works_1.png)
![Step 1](docs/images/how_it_works_2.png)
![Step 2](docs/images/how_it_works_3.png)
![Step 3](docs/images/how_it_works_4.png)
![Step 4](docs/images/how_it_works_5.png)

## Risk Scoring

| Level | Score | Points |
|-------|-------|--------|
| **LOW** | 0-25 | Safe |
| **MEDIUM** | 26-60 | Caution |
| **HIGH** | 61+ | Not recommended |

**Components:** Contraindicated (50) • Major (30) • Moderate (15) • Minor (5) • Mismatch (40) • Side Effects (1-30)

## Installation

```bash
git clone <repo-url>
cd medguard_v1

# Setup
uv venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv sync

# Configure
cp .env.example .env

# Database
python manage.py migrate
python manage.py migrate_hardcoded_data

# Run
python manage.py runserver
```

Visit http://127.0.0.1:8000

## Usage

**Web:** Enter symptoms → medication → current meds → get assessment

**Testing:**
```bash
python run_comprehensive_tests.py --level basic
python manual_test.py --scenario high_risk
```

## API

```python
from medguard_app.orchestrator import get_decision_pipeline

result = get_decision_pipeline().evaluate(
    symptoms=["headache", "fever"],
    proposed_drug="ibuprofen",
    existing_drugs=["lisinopril"]
)
# Returns: risk_score, risk_level, findings, recommendations, alternatives
```

## Tech Stack

Django 6.0 • ChromaDB • Sentence Transformers • RapidFuzz • SQLite/MySQL

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests.

## Documentation

- [Manual Test Inputs](MANUAL_TEST_INPUTS.md) - Copy-paste test scenarios
- [Testing Guide](TESTING_GUIDE.md) - Comprehensive testing instructions
- [Test Data Documentation](test_data_comprehensive.md) - Detailed test case specs

## Disclaimer

Educational purposes only. Not a substitute for professional medical advice.

## License

MIT License - See [LICENSE](LICENSE) for details
