import shutil
import re
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Keem\Desktop\projects\medguard_v1")
SERVICES_DIR = BASE_DIR / "medguard_app" / "services"

print("=" * 70)
print("MEDGUARD COMPLETE REFACTORING SCRIPT")
print("=" * 70)
print("\nThis script will:")
print("1. Replace old service files with new database-driven versions")
print("2. Remove all comments (keeping docstrings)")
print("3. Remove all emoji icons")
print("4. Clean up code formatting")
print("\n" + "=" * 70)

def remove_inline_comments(text):
    lines = []
    in_docstring = False
    docstring_char = None
    
    for line in text.split('\n'):
        stripped = line.lstrip()
        
        if '"""' in line or "'''" in line:
            if not in_docstring:
                lines.append(line)
                if '"""' in line and line.count('"""') == 1:
                    in_docstring = True
                    docstring_char = '"""'
                elif "'''" in line and line.count("'''") == 1:
                    in_docstring = True
                    docstring_char = "'''"
                continue
            else:
                lines.append(line)
                if docstring_char and docstring_char in line:
                    in_docstring = False
                continue
        
        if in_docstring:
            lines.append(line)
            continue
        
        if stripped.startswith('#'):
            continue
        
        if '#' in line and not ('"""' in line or "'''" in line):
            before_hash = line.split('#')[0]
            if before_hash.strip():
                lines.append(before_hash.rstrip())
            continue
        
        lines.append(line)
    
    return '\n'.join(lines)

def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  
        "\U0001F300-\U0001F5FF"  
        "\U0001F680-\U0001F6FF"  
        "\U0001F1E0-\U0001F1FF"  
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "\u2300-\u23FF"
        "\u2B50"
        "\u2705"  
        "\u274C"  
        "\u2757"
        "\u26A0"  
        "\u2713"
        "\u2717"
        "\U0001F4A5"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

print("\n[STEP 1] Replacing service files with database-driven versions...")
print("-" * 70)

files_to_replace = {
    "treatment_validator.py": "treatment_validator_new.py",
    "interaction_checker.py": "interaction_checker_new.py",
    "side_effect_analyzer.py": "side_effect_analyzer_new.py",
    "drug_alternatives.py": "drug_alternatives_new.py",
}

replaced_count = 0
for old_name, new_name in files_to_replace.items():
    old_file = SERVICES_DIR / old_name
    new_file = SERVICES_DIR / new_name
    backup_file = SERVICES_DIR / f"{old_name}.backup"
    
    if old_file.exists() and new_file.exists():
        print(f"  Processing {old_name}...")
        shutil.copy2(old_file, backup_file)
        shutil.copy2(new_file, old_file)
        new_file.unlink()
        print(f"    ✓ Replaced (backup: {backup_file.name})")
        replaced_count += 1
    else:
        print(f"  ⚠ Skipping {old_name} - files not ready")

print(f"\n  Replaced {replaced_count} service files")

print("\n[STEP 2] Removing comments and emojis from all Python files...")
print("-" * 70)

files_to_clean = [
    SERVICES_DIR / "risk_engine.py",
    SERVICES_DIR / "symptom_analyzer.py",
    SERVICES_DIR / "llm_service.py",
    BASE_DIR / "medguard_app" / "orchestrator" / "decision_pipeline.py",
    BASE_DIR / "medguard_app" / "views.py",
    BASE_DIR / "medguard_app" / "utils" / "normalizers.py",
    BASE_DIR / "apps" / "data_access" / "management" / "commands" / "migrate_hardcoded_data.py",
    BASE_DIR / "medguard_app" / "apps.py",
    BASE_DIR / "medguard_app" / "management" / "commands" / "preload_model.py",
]

cleaned_count = 0
for filepath in files_to_clean:
    if filepath.exists():
        try:
            content = filepath.read_text(encoding='utf-8')
            cleaned = remove_inline_comments(content)
            cleaned = remove_emojis(cleaned)
            
            if cleaned != content:
                filepath.write_text(cleaned, encoding='utf-8')
                print(f"  ✓ Cleaned: {filepath.relative_to(BASE_DIR)}")
                cleaned_count += 1
            else:
                print(f"  - No changes: {filepath.relative_to(BASE_DIR)}")
        except Exception as e:
            print(f"  ✗ Error cleaning {filepath.name}: {e}")
    else:
        print(f"  ⚠ Not found: {filepath.relative_to(BASE_DIR)}")

print(f"\n  Cleaned {cleaned_count} files")

print("\n" + "=" * 70)
print("REFACTORING COMPLETE!")
print("=" * 70)
print("\nSummary:")
print(f"  • Replaced {replaced_count} service files with database-driven versions")
print(f"  • Cleaned {cleaned_count} files (removed comments and emojis)")
print(f"\nBackup files saved with .backup extension")
print(f"To revert service changes: copy .backup files to original names")
print("\nNext steps:")
print("  1. Run tests: python manage.py test")
print("  2. Check app functionality")
print("  3. Remove .backup files when confident")
