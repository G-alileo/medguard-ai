# MedGuard AI - Developer Quick Reference

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  (Frontend - React/Vue - To be implemented in Phase 4)      │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  ┌────────────────┐         ┌──────────────────────┐       │
│  │  API Endpoints │ ←────→  │ Decision Pipeline    │       │
│  │  (views.py)    │         │ (orchestrator/)      │       │
│  └────────────────┘         └──────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                      │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Input         │  │ Treatment    │  │ Interaction     │  │
│  │ Normalizer    │  │ Validator    │  │ Checker         │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Side Effect   │  │ Risk Engine  │  │ LLM Service     │  │
│  │ Analyzer      │  │ (CORE)       │  │ (Explanations)  │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   MySQL     │  │  ChromaDB    │  │  Repositories    │   │
│  │ (Structured)│  │  (Vectors)   │  │  (Data Access)   │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Decision Pipeline (MAIN ENTRY POINT)
```python
from medguard_app.orchestrator import get_decision_pipeline

pipeline = get_decision_pipeline()
result = pipeline.evaluate(
    symptoms=["headache", "fever"],
    proposed_drug="acetaminophen",
    existing_drugs=["aspirin"]
)
```

**Returns:**
- `risk_score` (int): 0-100+ points
- `risk_level` (str): "LOW" | "MEDIUM" | "HIGH"
- `findings` (dict): Details about treatment, interactions, side effects
- `recommendation` (dict): Action to take, whether to consult doctor
- `explanation` (str): Natural language explanation
- `metadata` (dict): Evaluation ID, timestamp, processing time

---

### 2. Risk Engine (CORE SCORING LOGIC)

**Never modify the risk scoring without discussing first - this is the HEART of the system**

```python
from medguard_app.services.risk_engine import RiskEngine

engine = RiskEngine()
result = engine.calculate_risk_score(
    treatment_result={...},
    interactions=[...],
    side_effect_analysis={...}
)
```

**Scoring Rules:**
```python
WEIGHTS = {
    "no_treatment_indication": 40,      # Drug won't treat the symptoms
    "interaction_critical": 50,         # Life-threatening interaction
    "interaction_high": 30,             # Serious interaction
    "interaction_medium": 15,           # Moderate interaction
    "interaction_low": 5,               # Minor interaction
    "side_effect_overlap_max": 30,     # Side effects match symptoms (capped)
}

THRESHOLDS = {
    "low_max": 25,      # 0-25: LOW risk
    "medium_max": 60,   # 26-60: MEDIUM risk
                        # 61+: HIGH risk
}
```

---

### 3. Service Layer

#### InputNormalizer
```python
from medguard_app.utils.normalizers import get_input_normalizer

normalizer = get_input_normalizer()

# Normalize single drug
result = normalizer.normalize_drug_name("TYLENOL")
# → NormalizationResult(canonical_name="acetaminophen", confidence=1.0)

# Normalize symptom
symptom = normalizer.normalize_symptom("head pain")
# → "headache"

# Normalize all inputs at once
inputs = normalizer.normalize_inputs(
    symptoms=["head pain", "fever"],
    drug="Tylenol",
    existing_drugs=["Advil"]
)
# → {"drug": {...}, "symptoms_canonical": [...], ...}
```

#### TreatmentValidator
```python
from medguard_app.services.treatment_validator import TreatmentValidator

validator = TreatmentValidator()

# Check if drug treats symptom
result = validator.does_drug_treat_symptom("acetaminophen", "headache")
# → {"treats": True, "confidence": "high", "matched_symptom": "headache"}

# Validate drug for multiple symptoms
result = validator.validate_treatment_for_symptoms(
    "acetaminophen",
    ["headache", "fever"]
)
# → {"overall_treats": True, "confidence": "high", "details": [...]}
```

#### InteractionChecker
```python
from medguard_app.services.interaction_checker import InteractionChecker

checker = InteractionChecker()

# Check single interaction
result = checker.check_drug_pair("warfarin", "aspirin")
# → {"severity": "high", "description": "...", "mechanism": "..."}

# Check all interactions
results = checker.check_all_interactions("warfarin", ["aspirin", "ibuprofen"])
# → [{"proposed_drug": "warfarin", "existing_drug": "aspirin", ...}, ...]
```

#### SideEffectAnalyzer
```python
from medguard_app.services.side_effect_analyzer import SideEffectAnalyzer

analyzer = SideEffectAnalyzer()

result = analyzer.analyze_side_effect_overlap(
    drug_name="acetaminophen",
    symptoms=["headache", "nausea"]
)
# → {"overlapping_count": 1, "overlapping_symptoms": ["nausea"], "risk_increase": 15}
```

---

### 4. API Endpoints

#### Evaluate Drug Safety
```bash
POST /api/evaluate/

Request:
{
  "symptoms": ["headache", "fever"],
  "proposed_drug": "acetaminophen",
  "existing_drugs": ["aspirin"]
}

Response:
{
  "success": true,
  "data": {
    "risk_score": 30,
    "risk_level": "MEDIUM",
    "normalized_inputs": {...},
    "findings": {...},
    "recommendation": {...},
    "explanation": "...",
    "metadata": {...}
  }
}
```

#### Health Check
```bash
GET /api/health/

Response:
{
  "status": "healthy",
  "service": "medguard-api",
  "version": "1.0.0"
}
```

---

## Testing

### Run All Tests
```bash
# Component verification
python scripts/verify_business_layer.py

# API integration tests
python scripts/test_api.py

# Unit tests (pytest)
pytest medguard_app/tests/test_decision_pipeline.py -v
```

### Manual Testing
```bash
# Start server
python manage.py runserver

# In another terminal, test with curl:
curl -X POST http://localhost:8000/api/evaluate/ \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": ["headache"],
    "proposed_drug": "acetaminophen",
    "existing_drugs": []
  }'
```

---

## Common Tasks

### Adding a New Drug to Treatment Validator

Edit `medguard_app/services/treatment_validator.py`:

```python
KNOWN_TREATMENTS = {
    # ... existing drugs ...
    "new_drug_name": [
        "symptom1",
        "symptom2",
        "symptom3",
    ],
}
```

### Adding a New Drug Interaction

Edit `medguard_app/services/interaction_checker.py`:

```python
KNOWN_INTERACTIONS = {
    # ... existing interactions ...
    ("drug_a", "drug_b"): {
        "severity": "high",  # critical, high, medium, low
        "description": "Description of the interaction",
        "mechanism": "How it happens",
        "clinical_effects": "What happens clinically",
    },
}
```

### Adding a New Symptom Mapping

Edit `medguard_app/utils/normalizers.py`:

```python
SYMPTOM_MAPPINGS = {
    # ... existing mappings ...
    "user variation": "canonical_form",
    "tummy pain": "abdominal pain",
}
```

### Adjusting Risk Thresholds

Edit `medguard_app/services/risk_engine.py`:

```python
THRESHOLDS = {
    "low_max": 25,      # Change these values
    "medium_max": 60,   # to adjust risk levels
}
```

**WARNING:** Do NOT change weights without discussing - these are carefully calibrated!

---

## Debugging

### Enable Debug Logging

In `.env`:
```bash
LOG_LEVEL=DEBUG
```

Or in code:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Pipeline Results

```python
from medguard_app.orchestrator import get_decision_pipeline
import json

pipeline = get_decision_pipeline()
result = pipeline.evaluate(
    symptoms=["headache"],
    proposed_drug="acetaminophen",
    existing_drugs=[]
)

# Pretty print the result
print(json.dumps(result, indent=2))

# Check score breakdown
print(result["score_breakdown"])
# → {"treatment_mismatch": 0, "interactions": 0, "side_effect_overlap": 0}
```

### Test Individual Components

```python
# Test normalizer
from medguard_app.utils.normalizers import get_input_normalizer
normalizer = get_input_normalizer()
print(normalizer.normalize_drug_name("tylenol"))

# Test treatment validator
from medguard_app.services.treatment_validator import TreatmentValidator
validator = TreatmentValidator()
print(validator.does_drug_treat_symptom("acetaminophen", "headache"))

# Test interaction checker
from medguard_app.services.interaction_checker import InteractionChecker
checker = InteractionChecker()
print(checker.check_drug_pair("warfarin", "aspirin"))
```

---

## File Structure

```
medguard_v1/
├── medguard_app/              # Business logic layer
│   ├── utils/
│   │   └── normalizers.py     # Input normalization
│   ├── services/
│   │   ├── treatment_validator.py
│   │   ├── interaction_checker.py
│   │   ├── side_effect_analyzer.py
│   │   ├── risk_engine.py     # ⭐ CORE SCORING
│   │   └── llm_service.py
│   ├── orchestrator/
│   │   └── decision_pipeline.py  # ⭐ MAIN BRAIN
│   ├── tests/
│   │   └── test_decision_pipeline.py
│   ├── views.py               # API endpoints
│   └── urls.py
│
├── data_access/               # Data layer
│   ├── models/               # Django ORM models
│   ├── repositories/         # Data access patterns
│   └── vector_store/         # ChromaDB interface
│
├── pipeline/                  # Data processing
│   ├── processing/           # Normalizers, cleaners
│   └── loaders/              # Data loaders
│
├── scripts/
│   ├── test_api.py           # API integration tests
│   └── verify_business_layer.py  # Component tests
│
└── docs/
    └── phase_3_completion_report.md
```

---

## Important Constants

### Risk Levels
```python
LOW = "LOW"        # 0-25 points: Safe to use
MEDIUM = "MEDIUM"  # 26-60 points: Use with caution
HIGH = "HIGH"      # 61+ points: Not recommended
```

### Interaction Severities
```python
CRITICAL = "critical"  # +50 points - Contraindicated
HIGH = "high"          # +30 points - Serious risk
MEDIUM = "medium"      # +15 points - Moderate risk
LOW = "low"            # +5 points - Minor risk
```

### Confidence Levels
```python
HIGH = "high"      # Strong evidence
MEDIUM = "medium"  # Moderate evidence
LOW = "low"        # Weak evidence
```

---

## LLM Integration

### Current Mode: MOCK (fallback)

When `DEEPSEEK_API_KEY` is not set, uses template-based explanations.

### Enable Real LLM

In `.env`:
```bash
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### LLM Behavior

**CRITICAL:** The LLM ONLY generates explanations. It does NOT:
- Calculate risk scores
- Determine risk levels
- Make medical decisions

All scoring is deterministic via `RiskEngine`.

---

## Performance

### Typical Processing Times

- Input normalization: ~10ms
- Treatment validation: ~5ms
- Interaction checking: ~10ms
- Risk calculation: ~5ms
- Vector retrieval: ~50ms (if loaded)
- LLM explanation: ~500-2000ms (real mode) / ~1ms (mock mode)

**Total:** ~50-100ms (mock) or ~600-2100ms (with real LLM)

### Optimization Tips

1. Use mock mode during development (faster iteration)
2. Vector store is optional - disable if not needed
3. Cache normalizer instances (already singleton)
4. Batch API calls if processing multiple drugs

---

## Security Notes

1. **CSRF Exempt:** API endpoints have CSRF exemption for REST calls
   - In production, use token-based auth instead

2. **No Authentication:** Currently no user auth
   - Add authentication before public deployment

3. **Input Validation:** Basic validation in views
   - Consider adding rate limiting in production

4. **Secret Key:** Change `DJANGO_SECRET_KEY` in production

---

## Next Steps

1. **Configure DeepSeek API** for real explanations
2. **Add Authentication** (JWT, OAuth, etc.)
3. **Build Frontend** (React/Vue)
4. **Deploy to Production** (Docker, AWS, etc.)
5. **Add Monitoring** (logging, metrics, alerts)
6. **Expand Knowledge Base** (more drugs, interactions)

---

**Questions? Issues?**
- Check `docs/phase_3_completion_report.md` for detailed documentation
- Run `python scripts/verify_business_layer.py` to verify setup
- Check logs with `LOG_LEVEL=DEBUG`
