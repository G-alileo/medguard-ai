# Manual Testing Input Data for MedGuard

Copy and paste these inputs directly into your MedGuard system to test different scenarios.

---

## LEVEL 1: BASIC SAFE SCENARIOS
*Expected: All LOW risk*

### Test 1.1: Simple Headache Relief
**Symptoms:** headache
**Proposed Drug:** ibuprofen
**Current Medications:** (leave empty)

### Test 1.2: Fever Treatment
**Symptoms:** fever
**Proposed Drug:** acetaminophen
**Current Medications:** (leave empty)

### Test 1.3: Allergy Relief
**Symptoms:** sneezing, runny nose
**Proposed Drug:** cetirizine
**Current Medications:** (leave empty)

### Test 1.4: Stomach Issues
**Symptoms:** nausea
**Proposed Drug:** ondansetron
**Current Medications:** (leave empty)

### Test 1.5: Cough Relief
**Symptoms:** cough
**Proposed Drug:** dextromethorphan
**Current Medications:** (leave empty)

---

## LEVEL 2: MODERATE COMPLEXITY
*Expected: Mix of LOW and MEDIUM risk*

### Test 2.1: Cold with Supplements
**Symptoms:** fever, headache, body aches
**Proposed Drug:** ibuprofen
**Current Medications:** vitamin d

### Test 2.2: Pain with Blood Pressure Med (INTERACTION)
**Symptoms:** back pain
**Proposed Drug:** ibuprofen
**Current Medications:** lisinopril

### Test 2.3: Sleep Issues with Antidepressant
**Symptoms:** insomnia
**Proposed Drug:** diphenhydramine
**Current Medications:** sertraline

### Test 2.4: Heartburn with Other Meds
**Symptoms:** heartburn
**Proposed Drug:** ranitidine
**Current Medications:** calcium carbonate

### Test 2.5: Arthritis Pain with Protection
**Symptoms:** arthritis pain
**Proposed Drug:** naproxen
**Current Medications:** omeprazole

---

## LEVEL 3: HIGH-RISK SCENARIOS
*Expected: HIGH risk warnings*

### Test 3.1: MAJOR BLEEDING RISK
**Symptoms:** headache
**Proposed Drug:** aspirin
**Current Medications:** warfarin

### Test 3.2: CNS DEPRESSION RISK
**Symptoms:** anxiety
**Proposed Drug:** alprazolam
**Current Medications:** oxycodone, zolpidem

### Test 3.3: SEROTONIN SYNDROME RISK
**Symptoms:** depression
**Proposed Drug:** fluoxetine
**Current Medications:** tramadol, trazodone

### Test 3.4: TREATMENT MISMATCH
**Symptoms:** fever, cough, fatigue
**Proposed Drug:** amoxicillin
**Current Medications:** (leave empty)

### Test 3.5: CARDIAC RISK
**Symptoms:** chest pain
**Proposed Drug:** nitroglycerin
**Current Medications:** sildenafil

---

## LEVEL 4: COMPLEX SCENARIOS

### Test 4.1: Multiple Pain Meds (DUPLICATION)
**Symptoms:** pain
**Proposed Drug:** ibuprofen
**Current Medications:** naproxen

### Test 4.2: Kidney Concern
**Symptoms:** pain
**Proposed Drug:** ibuprofen
**Current Medications:** furosemide, lisinopril

### Test 4.3: Elderly Anticholinergic Risk
**Symptoms:** insomnia
**Proposed Drug:** diphenhydramine
**Current Medications:** oxybutynin, amitriptyline

### Test 4.4: QT Prolongation Risk
**Symptoms:** nausea
**Proposed Drug:** ondansetron
**Current Medications:** azithromycin, ciprofloxacin

---

## SYMPTOM NORMALIZATION TESTS
*Test how system handles different ways of saying the same thing*

### Test 5.1: Symptom Variations
**Symptoms:** head pain, stomach ache, feeling sick
**Proposed Drug:** acetaminophen
**Current Medications:** (leave empty)

### Test 5.2: Brand Name Variations
**Symptoms:** headache
**Proposed Drug:** tylenol
**Current Medications:** advil

### Test 5.3: Medical Terms
**Symptoms:** pyrexia, cephalgia, myalgia
**Proposed Drug:** ibuprofen
**Current Medications:** (leave empty)

---

## ERROR HANDLING TESTS

### Test 6.1: Unknown Drug
**Symptoms:** headache
**Proposed Drug:** xyz_unknown_medication
**Current Medications:** (leave empty)

### Test 6.2: Very Long Input
**Symptoms:** headache, nausea, dizziness, fatigue, anxiety, insomnia, back pain, joint pain, muscle aches, fever
**Proposed Drug:** ibuprofen
**Current Medications:** vitamin d, vitamin c, calcium

---

## REAL-WORLD SCENARIOS

### Test 7.1: Common Cold
**Symptoms:** runny nose, sneezing, sore throat, fatigue
**Proposed Drug:** pseudoephedrine
**Current Medications:** (leave empty)

### Test 7.2: Migraine Sufferer
**Symptoms:** severe headache, nausea, sensitivity to light
**Proposed Drug:** sumatriptan
**Current Medications:** propranolol

### Test 7.3: Elderly Patient
**Symptoms:** arthritis pain
**Proposed Drug:** ibuprofen
**Current Medications:** metoprolol, atorvastatin, aspirin, lisinopril

### Test 7.4: Young Adult with Anxiety
**Symptoms:** anxiety, panic attacks
**Proposed Drug:** lorazepam
**Current Medications:** sertraline

### Test 7.5: Post-Surgical Patient
**Symptoms:** severe pain
**Proposed Drug:** oxycodone
**Current Medications:** acetaminophen, ibuprofen

---

## QUICK REFERENCE FOR TESTING

### Expected LOW Risk (Safe)
- Single symptoms + appropriate OTC meds
- No interactions with safe combinations
- Proper symptom-drug matches

### Expected MEDIUM Risk (Caution)
- Minor to moderate drug interactions
- Duplicate therapies (multiple antihistamines)
- Some side effect overlaps

### Expected HIGH Risk (Dangerous)
- Major drug interactions (warfarin + aspirin)
- CNS depressant combinations
- Treatment mismatches (antibiotics for viral)
- Serious contraindications

---

## STEP-BY-STEP TESTING GUIDE

1. **Start Simple**: Use Level 1 tests first to verify basic functionality
2. **Check Normalization**: Try symptom variations to see if system handles different terms
3. **Test Interactions**: Use Level 2 and 3 to verify interaction detection
4. **Verify Warnings**: Look for appropriate warnings and risk levels
5. **Check Alternatives**: See if system suggests safer alternatives for high-risk scenarios
6. **Test Edge Cases**: Try unknown drugs, empty fields, very long inputs

---

## WHAT TO LOOK FOR

### Risk Assessment
- ✅ **LOW risk**: Score 0-25, green indicators
- ⚠️ **MEDIUM risk**: Score 26-60, yellow warnings
- 🚨 **HIGH risk**: Score 61+, red alerts

### Key Information
- Drug found in database: Yes/No
- Treats symptoms: Yes/No with confidence level
- Number of interactions detected
- Specific side effect warnings
- Alternative medication suggestions
- Professional consultation recommendations

### Performance
- Response time (should be under 5 seconds)
- No error messages or crashes
- Consistent results when re-testing same inputs

Copy any of these test scenarios directly into your MedGuard system to see how it performs!