# MedGuard AI - Data Inspection Report

## Executive Summary

This report documents the analysis of 5 data sources in `/data/raw/` for the MedGuard AI drug risk assessment system. Total data volume: **~3.8GB** across **~1.1 million records** (MVP scope: 3 JSON files per source, expandable later).

---

## 1. Data Source Inventory

| Source | Format | Files | Size | Records |
|--------|--------|-------|------|---------|
| SIDER Dataset | CSV | 1 | 41KB | 650 |
| ADR Synthetic Data | CSV | 1 | 72MB | 1,000,000 |
| FDA Adverse Events (CSV) | CSV | 1 | 999KB | 10,000 |
| OpenFDA Drug Events | JSON | 3 | 1.8GB | ~36,000 |
| OpenFDA Drug Labels | JSON | 3 | 1.9GB | ~60,000 |

---

## 2. Detailed File Analysis

### 2.1 SIDER Dataset (SIDER_DATASET_KAGGLE/drug_df.csv)

**Purpose:** Links drugs to adverse reactions (side effects)

**Schema:**
| Column | Type | Nulls | Unique Values | Description |
|--------|------|-------|---------------|-------------|
| primaryid | Integer | 0 | 146 | Report identifier |
| drugname | String | 0 | 79 | Drug name (lowercase) |
| pt | String | 0 | 258 | Preferred Term (adverse reaction) |
| role_cod | String | 0 | 1 | Role code (all "PS" = Primary Suspect) |
| age | Float | 60 (9%) | 65 | Patient age |
| sex | String | 57 (9%) | 2 | Patient sex (F/M) |
| drug_id | String | 0 | 79 | CID identifier (PubChem) |

**Sample Rows:**
```
primaryid,drugname,pt,role_cod,age,sex,drug_id
184614762,linezolid,hyperkalaemia,PS,71.0,F,CID100003929
208493885,pregabalin,panic reaction,PS,59.0,F,CID100125889
177156745,fluoxetine,myoclonus,PS,,F,CID100003386
```

**Key Observations:**
- Drug names are lowercase, providing some normalization
- Contains PubChem CID identifiers for external linking
- Good coverage of common drugs (79 unique)
- ~9% null values for demographic data (acceptable)

---

### 2.2 ADR Synthetic Data (Adverse Drug Reaction (ADR) Reporting/synthetic_drug_data.csv)

**Purpose:** Simulated adverse drug reaction reports with concomitant drug data

**Schema:**
| Column | Type | Nulls | Unique Values | Description |
|--------|------|-------|---------------|-------------|
| ReportID | String | 0 | 1,000,000 | Unique report ID |
| PatientAge | Integer | 0 | 73 | Patient age (18-90) |
| Gender | String | 0 | 3 | Male/Female/Other |
| DrugName | String | 0 | 20 | Primary drug (capitalized) |
| Dosage | String | 0 | ~1000 | Dosage with unit (e.g., "658mg") |
| DurationDays | Integer | 0 | 41 | Treatment duration |
| ConcomitantDrugs | String | ~43% | ~2000+ | Comma-separated drug list |
| ADR_Code | String | 0 | 12 | MedDRA ADR code |
| Seriousness | String | 0 | 4 | mild/moderate/severe/life-threatening |
| OnsetDays | Integer | 0 | 28 | Days until ADR onset |

**Sample Rows:**
```
ReportID,PatientAge,Gender,DrugName,Dosage,DurationDays,ConcomitantDrugs,ADR_Code,Seriousness,OnsetDays
REP-VJpHH7RG,52,Other,Ibuprofen,658mg,31,"Simvastatin, Fluoxetine, Gabapentin",10016256,mild,12
REP-xZHEIV6F,64,Male,Atorvastatin,359mg,33,,10019211,mild,5
REP-vzYm2NEH,72,Female,Prednisone,46mg,29,"Metformin, Lisinopril",10013968,mild,6
```

**Key Observations:**
- **Critical for drug interactions:** ConcomitantDrugs field shows drugs taken together
- Uses MedDRA ADR codes (need code-to-description mapping)
- Limited drug variety (20 drugs) - synthetic/simulated data
- Consistent capitalization (Title Case)

**ADR Code Distribution (sample):**
- 10013968, 10037660, 10016256 most frequent (need MedDRA dictionary)

---

### 2.3 FDA Adverse Events CSV (FDA Drug Adverse Event Reports/FDA_Drug_Adverse_Events.csv)

**Purpose:** Simplified FDA adverse event reports

**Schema:**
| Column | Type | Nulls | Unique Values | Description |
|--------|------|-------|---------------|-------------|
| report_date | String | 0 | 8 | Date (YYYYMMDD format) |
| serious | Integer | 0 | 2 | 1=serious, 2=not serious |
| sex | Integer | 74 (0.7%) | 3 | 1=Male, 2=Female, 0=Unknown |
| age | Integer | 3350 (33%) | 104 | Patient age |
| drugs | String | 0 | 4773 | Drug(s) involved (semicolon-separated) |
| reactions | String | 0 | 6037 | Reaction(s) (semicolon-separated) |
| outcome | String | 10000 (100%) | 0 | **EMPTY - unusable** |

**Sample Rows:**
```
report_date,serious,sex,age,drugs,reactions,outcome
20080707,1,1,26,DURAGESIC-100,DRUG ADMINISTRATION ERROR; OVERDOSE,
20140306,1,2,77,BONIVA,Vomiting; Diarrhoea; Arthralgia; Headache,
20140312,2,1,,LYRICA,Drug ineffective,
```

**Key Observations:**
- Drug names are UPPERCASE (brand names)
- Multiple drugs per record (polypharmacy cases valuable for interactions)
- Reactions are human-readable text
- **High null rate for age (33%) and outcome (100%)**
- Good variety of drugs (4773 unique)

---

### 2.4 OpenFDA Drug Events (drug-events/*.json)

**Purpose:** Comprehensive adverse event reports with structured drug and reaction data

**File Structure:**
```
drug-events/
  drug-event-0001-of-0028.json (3 files present, 28 total expected)
  ...
```

**Top-Level Schema:**
```json
{
  "meta": { "results": { "skip": 0, "limit": 12000, "total": 333446 } },
  "results": [ /* array of event reports */ ]
}
```

**Event Report Schema (key fields):**
| Field Path | Type | Description |
|------------|------|-------------|
| safetyreportid | String | Unique report ID |
| serious | String | 1=serious, 2=not serious |
| seriousnessdeath | String | 1=death, 2=no death |
| seriousnesshospitalization | String | 1=hospitalized |
| patient.patientsex | String | 1=Male, 2=Female |
| patient.patientagegroup | String | Age group code |
| patient.reaction[].reactionmeddrapt | String | MedDRA preferred term |
| patient.reaction[].reactionoutcome | String | Outcome code |
| patient.drug[].medicinalproduct | String | Drug name as reported |
| patient.drug[].drugindication | String | Why drug was taken |
| patient.drug[].drugcharacterization | String | 1=Suspect, 2=Concomitant, 3=Interacting |
| patient.drug[].activesubstance.activesubstancename | String | Active ingredient |
| patient.drug[].openfda.brand_name[] | Array | Brand names |
| patient.drug[].openfda.generic_name[] | Array | Generic names |
| patient.drug[].openfda.rxcui[] | Array | RxNorm CUI identifiers |

**Sample Drug Entry (openfda sub-object):**
```json
{
  "brand_name": ["LENALIDOMIDE", "REVLIMID"],
  "generic_name": ["LENALIDOMIDE"],
  "manufacturer_name": ["Celgene Corporation", ...],
  "rxcui": ["483533", "789765"],
  "pharm_class_epc": ["Immunomodulator"]
}
```

**Key Observations:**
- **RICHEST DATA SOURCE** - contains brand/generic name mapping
- RxCUI identifiers enable cross-referencing with RxNorm
- **drugcharacterization field identifies drug interactions** (value 3)
- MedDRA reaction codes with human-readable text
- Seriousness sub-classification (death, hospitalization, disability)

**Top Reactions (sample 1000 events):**
1. Adverse drug reaction (133)
2. Off label use (58)
3. Product dose omission issue (44)
4. Haemorrhage (39)
5. Drug ineffective (38)

---

### 2.5 OpenFDA Drug Labels (drug-label/*.json)

**Purpose:** Official FDA drug labeling with comprehensive prescribing information

**File Structure:**
```
drug-label/
  drug-label-0001-of-0013.json (3 files present, 13 total expected)
  ...
```

**Label Schema (41 fields, key ones shown):**
| Field | Type | Availability | Description |
|-------|------|--------------|-------------|
| id | String | 100% | Unique label ID |
| set_id | String | 100% | SPL Set ID |
| effective_time | String | 100% | Label effective date |
| indications_and_usage | Array[String] | 100% | What drug treats |
| contraindications | Array[String] | 54% | When NOT to use |
| warnings_and_cautions | Array[String] | 40% | Safety warnings |
| adverse_reactions | Array[String] | 55% | Known side effects |
| drug_interactions | Array[String] | 51% | **CRITICAL: Interaction info** |
| overdosage | Array[String] | 53% | Overdose information |
| boxed_warning | Array[String] | 28% | Most serious warnings |
| openfda.brand_name[] | Array | varies | Brand names |
| openfda.generic_name[] | Array | varies | Generic names |
| openfda.substance_name[] | Array | varies | Active substances |
| openfda.rxcui[] | Array | varies | RxNorm identifiers |

**Sample Drug Interaction Text:**
```
"7 DRUG INTERACTIONS
- Avoid concomitant use with aliskiren in patients with eGFR < 60
- Potassium-sparing diuretics: May lead to increased serum potassium
- NSAIDs: May lead to increased risk of renal impairment
- Lithium: Increased risk of lithium toxicity"
```

**Key Observations:**
- **PRIMARY SOURCE FOR VECTOR EMBEDDINGS** - rich narrative text
- Contains structured drug interaction warnings
- Only 51% have drug_interactions field populated
- 28% have boxed_warning (most serious drugs)
- Multiple brand/generic name mappings available

---

## 3. Cross-Dataset Analysis

### 3.1 Drug Name Overlap

| Dataset A | Dataset B | Overlap | Notes |
|-----------|-----------|---------|-------|
| SIDER (79) | ADR Synthetic (20) | 13 | Common drugs like ibuprofen, metformin |
| SIDER (79) | FDA CSV (5276) | 72 | SIDER drugs well-represented in FDA |
| ADR Synthetic (20) | FDA CSV (5276) | 20 | All ADR drugs exist in FDA |
| **All Three** | - | **13** | Core overlap |

**Common Drugs Across All Sources:**
`amlodipine, amoxicillin, citalopram, fluoxetine, gabapentin, ibuprofen, losartan, metformin, omeprazole, prednisone, sertraline, simvastatin, warfarin`

### 3.2 Drug Naming Variations Found

| Variation Type | Example | Sources |
|----------------|---------|---------|
| Case | `ibuprofen` vs `IBUPROFEN` vs `Ibuprofen` | All |
| Brand vs Generic | `REVLIMID` vs `LENALIDOMIDE` | OpenFDA |
| Combination drugs | `ACETAMINOPHEN\HYDROCODONE` | OpenFDA Events |
| With strength | `DURAGESIC-100` | FDA CSV |
| Multiple substances | `Olanzapine and Fluoxetine` | Drug Labels |

### 3.3 Potential Linkage Keys

| Key Type | Present In | Linkability |
|----------|------------|-------------|
| Drug Name (normalized) | All | **Primary key** - requires normalization |
| RxCUI | OpenFDA Events, Labels | Excellent - standard identifier |
| PubChem CID | SIDER | Limited - only SIDER has this |
| MedDRA Code | ADR Synthetic, OpenFDA | Good for reaction linking |

---

## 4. Data Quality Issues

### 4.1 Critical Issues

| Issue | Source | Impact | Mitigation |
|-------|--------|--------|------------|
| Drug name inconsistency | All | Cannot join without normalization | Build normalization dictionary |
| MedDRA codes without descriptions | ADR Synthetic | Cannot display to users | Map codes to terms |
| Missing outcome field | FDA CSV | 100% null, unusable | Ignore this field |
| High age null rate | FDA CSV (33%) | Demographics incomplete | Accept partial data |

### 4.2 Data Quality Summary

| Source | Completeness | Consistency | Usability |
|--------|--------------|-------------|-----------|
| SIDER | Good (91%) | Excellent | High |
| ADR Synthetic | Excellent (100%) | Good | High |
| FDA CSV | Moderate (67%) | Good | Medium |
| OpenFDA Events | Good | Excellent | **Critical** |
| OpenFDA Labels | Moderate (51% for interactions) | Excellent | **Critical** |

---

## 5. File Relationship Diagram

```
                    +------------------+
                    |   DRUG LABELS    |
                    | (indications,    |
                    |  interactions,   |
                    |  warnings)       |
                    +--------+---------+
                             |
                    brand_name/generic_name/rxcui
                             |
                             v
+-------------+     +------------------+     +---------------+
|   SIDER     |     |   DRUG EVENTS    |     |   FDA CSV     |
| (drug-pt    |<--->| (reports with    |<--->| (simplified   |
|  mappings)  |     |  drugs/reactions)|     |  reports)     |
+------+------+     +--------+---------+     +-------+-------+
       |                     |                       |
       |          drug name (normalized)             |
       |                     |                       |
       +----------+----------+-----------+-----------+
                  |                      |
                  v                      v
         +----------------+      +----------------+
         | ADR SYNTHETIC  |      | NORMALIZATION  |
         | (concomitant   |      | DICTIONARY     |
         |  drug data)    |      | (brand/generic |
         +----------------+      |  mappings)     |
                                 +----------------+
```

---

## 6. Critical vs Nice-to-Have Fields

### 6.1 Critical Fields (Must Load)

| Source | Field | Reason |
|--------|-------|--------|
| Drug Labels | indications_and_usage | Core: what drug treats |
| Drug Labels | drug_interactions | Core: interaction warnings |
| Drug Labels | contraindications | Core: when NOT to use |
| Drug Labels | adverse_reactions | Core: known side effects |
| Drug Labels | boxed_warning | Core: most serious risks |
| Drug Labels | openfda.* | Links brand/generic names |
| Drug Events | patient.drug[].* | Drug-reaction associations |
| Drug Events | patient.reaction[].* | Adverse reaction data |
| SIDER | drugname, pt | Drug-side effect links |
| ADR Synthetic | ConcomitantDrugs | Drug combination data |

### 6.2 Nice-to-Have Fields

| Source | Field | Reason |
|--------|-------|--------|
| Drug Events | sending organization | Data provenance |
| Drug Labels | how_supplied | Not relevant to safety |
| FDA CSV | report_date | Historical context only |
| All | Demographics (age, sex) | For population filtering |

---

## 7. Recommendations for Phase 2

1. **Prioritize OpenFDA Drug Labels** - richest source for semantic search
2. **Build normalization dictionary FIRST** - using openfda.brand_name/generic_name mappings
3. **Create MedDRA code lookup table** - needed for ADR Synthetic data
4. **Process JSON files in batches** - 1.8GB + 1.9GB requires chunked processing
5. **Validate linkage** - verify all 13 common drugs link correctly before full load
