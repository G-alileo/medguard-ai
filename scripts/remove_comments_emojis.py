import re
import ast
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Keem\Desktop\projects\medguard_v1")

def remove_comments_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    in_docstring = False
    docstring_char = None
    
    for line in lines:
        stripped = line.lstrip()
        
        if '"""' in stripped or "'''" in stripped:
            if not in_docstring:
                cleaned_lines.append(line)
                if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in stripped else "'''"
                continue
            else:
                cleaned_lines.append(line)
                if docstring_char in stripped:
                    in_docstring = False
                continue
        
        if in_docstring:
            cleaned_lines.append(line)
            continue
        
        if stripped.startswith('#'):
            continue
        
        if '#' in line:
            code_part = line.split('#')[0]
            if code_part.strip():
                cleaned_lines.append(code_part.rstrip() + '\n')
            continue
        
        cleaned_lines.append(line)
    
    return ''.join(cleaned_lines)

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
        "\u2B06"
        "\u2B07"
        "\u27A1"
        "\u2B05"
        "\U0001F4A5"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

def clean_file(filepath):
    print(f"Cleaning: {filepath.relative_to(BASE_DIR)}")
    
    try:
        content = filepath.read_text(encoding='utf-8')
        
        content_no_emoji = remove_emojis(content)
        
        cleaned_content = remove_comments_from_file(filepath)
        
        cleaned_content_no_emoji = remove_emojis(cleaned_content)
        
        backup_path = filepath.with_suffix('.py.cleaned_backup')
        filepath.write_text(cleaned_content, encoding='utf-8')
        
        print(f"  ✓ Cleaned successfully")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

files_to_clean = [
    BASE_DIR / "medguard_app" / "orchestrator" / "decision_pipeline.py",
    BASE_DIR / "medguard_app" / "services" / "risk_engine.py",
    BASE_DIR / "medguard_app" / "services" / "symptom_analyzer.py",
    BASE_DIR / "medguard_app" / "services" / "llm_service.py",
    BASE_DIR / "medguard_app" / "views.py",
    BASE_DIR / "medguard_app" / "utils" / "normalizers.py",
    BASE_DIR / "apps" / "data_access" / "management" / "commands" / "migrate_hardcoded_data.py",
]

print("=" * 70)
print("REMOVING COMMENTS AND EMOJIS FROM PYTHON FILES")
print("=" * 70)
print()

success_count = 0
for filepath in files_to_clean:
    if filepath.exists():
        if clean_file(filepath):
            success_count += 1
    else:
        print(f"Skipping: {filepath.relative_to(BASE_DIR)} (not found)")

print()
print("=" * 70)
print(f"Cleaned {success_count} / {len(files_to_clean)} files successfully")
print("=" * 70)
