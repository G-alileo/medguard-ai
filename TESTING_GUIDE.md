# MedGuard Testing Quick Reference Guide

## Overview
This document provides a quick reference for testing the MedGuard software using the comprehensive test suite.

## Test Files Created

### 1. Test Data Files
- **`test_data_comprehensive.md`** - Complete documentation of all test scenarios
- **`test_cases_basic.json`** - Simple, low-risk test cases (5 tests)
- **`test_cases_moderate.json`** - Moderate complexity test cases (7 tests)
- **`test_cases_complex.json`** - High-risk, complex scenarios (7 tests)
- **`test_cases_edge.json`** - Edge cases and error handling (10 tests)

### 2. Test Scripts
- **`run_comprehensive_tests.py`** - Automated test runner for all test suites
- **`manual_test.py`** - Interactive testing for custom scenarios

---

## Quick Start Testing

### 1. Basic Automated Testing
```bash
# Run all test levels
python run_comprehensive_tests.py

# Run specific test level
python run_comprehensive_tests.py --level basic
python run_comprehensive_tests.py --level moderate
python run_comprehensive_tests.py --level complex
python run_comprehensive_tests.py --level edge

# Verbose output with detailed results
python run_comprehensive_tests.py --verbose

# Save results to file
python run_comprehensive_tests.py --output test_results.json
```

### 2. Manual/Interactive Testing
```bash
# Interactive mode - prompts for input
python manual_test.py

# Quick predefined scenarios
python manual_test.py --scenario basic
python manual_test.py --scenario high_risk
python manual_test.py --scenario allergy

# Custom command-line testing
python manual_test.py --symptoms "headache fever" --drug "ibuprofen"
python manual_test.py --symptoms "back pain" --drug "ibuprofen" --existing "lisinopril"

# List available scenarios
python manual_test.py --list-scenarios
```

---

## Test Level Progression

### Level 1: Basic Tests (5 tests)
**Purpose**: Verify core functionality works
- Single symptoms with appropriate medications
- No existing medications
- Expected: All LOW risk

**Examples**:
- Headache + Ibuprofen
- Fever + Acetaminophen
- Allergies + Cetirizine

### Level 2: Moderate Tests (7 tests)
**Purpose**: Test multiple symptoms and minor interactions
- Multiple symptoms
- Some current medications
- Minor interactions possible
- Expected: Mix of LOW and MEDIUM risk

**Examples**:
- Cold symptoms + Ibuprofen + Vitamin D
- Back pain + Ibuprofen + Lisinopril (interaction)
- Multiple antihistamines

### Level 3: Complex Tests (7 tests)
**Purpose**: High-risk scenarios and serious interactions
- Treatment mismatches
- Major drug interactions
- Polypharmacy scenarios
- Expected: Mostly HIGH risk

**Examples**:
- Warfarin + Aspirin (bleeding risk)
- Multiple CNS depressants
- Serotonin syndrome risks

### Level 4: Edge Cases (10 tests)
**Purpose**: Error handling and special scenarios
- Unknown drugs
- Empty inputs
- Input normalization
- Alternative recommendations
- Expected: Various outcomes, graceful error handling

### Level 5: Stress Tests (in comprehensive.md)
**Purpose**: Maximum complexity scenarios
- Cardiac emergencies
- Pregnancy considerations
- Organ dysfunction

---

## Expected Test Results

### Success Criteria
- **Basic Level**: 100% pass rate, all LOW risk
- **Moderate Level**: >80% pass rate, mix LOW/MEDIUM risk
- **Complex Level**: >70% pass rate, appropriate HIGH risk detection
- **Edge Cases**: Graceful error handling, no crashes

### Key Metrics to Monitor
1. **Pass Rate**: Tests completing without errors
2. **Risk Detection**: Appropriate risk levels assigned
3. **Performance**: Response times <5 seconds
4. **Validation**: Expected outcomes matching actual results

### Performance Benchmarks
- **Average Response Time**: <2 seconds
- **Complex Scenarios**: <5 seconds
- **Memory Usage**: Stable across test runs
- **No Memory Leaks**: During extended testing

---

## Interpreting Results

### Risk Level Thresholds
- **LOW (0-25 points)**: Generally safe combinations
- **MEDIUM (26-60 points)**: Caution advised, monitoring needed
- **HIGH (61+ points)**: Not recommended, serious risks

### Score Components
- **Treatment Mismatch**: 40 points (drug doesn't treat symptoms)
- **Major Interaction**: 30 points
- **Moderate Interaction**: 20 points
- **Minor Interaction**: 10 points
- **Side Effect Overlap**: 0-30 points (based on severity)

### Expected Findings
- **Drug Found**: Should be `true` for known medications
- **Treats Symptom**: Should match known indications
- **Interactions Found**: Count of detected interactions
- **Side Effect Warnings**: Specific overlap warnings

---

## Common Test Scenarios

### Safe Combinations (Expected LOW risk)
```
Symptoms: headache → Drug: acetaminophen → Existing: []
Symptoms: fever → Drug: ibuprofen → Existing: [vitamin d]
Symptoms: allergy → Drug: cetirizine → Existing: []
```

### Moderate Risk (Expected MEDIUM risk)
```
Symptoms: pain → Drug: ibuprofen → Existing: [lisinopril]
Symptoms: insomnia → Drug: diphenhydramine → Existing: [sertraline]
Symptoms: duplicate therapy scenarios
```

### High Risk (Expected HIGH risk)
```
Symptoms: headache → Drug: aspirin → Existing: [warfarin]
Symptoms: anxiety → Drug: alprazolam → Existing: [oxycodone, zolpidem]
Symptoms: treatment mismatches (antibiotics for viral symptoms)
```

---

## Troubleshooting

### Common Issues
1. **Django Setup Errors**: Ensure you're in the project root directory
2. **Module Import Errors**: Check Python path and virtual environment
3. **Database Errors**: Run migrations first: `python manage.py migrate`
4. **Missing Test Files**: Ensure all JSON files are in project root

### Debug Commands
```bash
# Check Django setup
python manage.py check

# Test pipeline directly
python manage.py shell
>>> from medguard_app.orchestrator.decision_pipeline import DecisionPipeline
>>> pipeline = DecisionPipeline()
>>> result = pipeline.evaluate(['headache'], 'ibuprofen', [])

# Run single test for debugging
python manual_test.py --scenario basic --verbose
```

### Performance Issues
- Use `--level basic` for quick smoke tests
- Monitor execution times in verbose mode
- Check system resources during complex tests

---

## Customizing Tests

### Adding New Test Cases
1. Edit appropriate JSON file (basic/moderate/complex/edge)
2. Follow the JSON structure format
3. Include expected outcomes for validation
4. Test individually before adding to suite

### Creating Custom Scenarios
```python
# Add to manual_test.py predefined scenarios
'my_scenario': {
    'symptoms': ['symptom1', 'symptom2'],
    'drug': 'drug_name',
    'existing_drugs': ['existing1', 'existing2']
}
```

### Test Data Format
```json
{
  "test_id": "unique_identifier",
  "name": "Human-readable test name",
  "level": "basic|moderate|complex|edge_case",
  "input": {
    "symptoms": ["symptom1", "symptom2"],
    "proposed_drug": "drug_name",
    "existing_drugs": ["drug1", "drug2"]
  },
  "expected": {
    "risk_level": "LOW|MEDIUM|HIGH",
    "treats_symptom": true|false,
    "interactions_found": 0,
    "has_alternatives": true|false
  }
}
```

---

## Integration with CI/CD

### Automated Testing Pipeline
```bash
# In CI/CD pipeline
python run_comprehensive_tests.py --level basic --output ci_results.json

# Check exit code for pass/fail
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests failed"
    exit 1
fi
```

### Regression Testing
- Run full suite on major changes
- Run basic suite on minor changes
- Monitor performance degradation
- Track test coverage metrics

---

## Next Steps

1. **Start with Basic Tests**: Ensure foundation is solid
2. **Progress Through Levels**: Build confidence incrementally
3. **Monitor Performance**: Track response times and resource usage
4. **Add Custom Scenarios**: Based on your specific use cases
5. **Automate in CI/CD**: For continuous validation

For detailed test case documentation, see `test_data_comprehensive.md`.