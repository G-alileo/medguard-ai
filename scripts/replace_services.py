import shutil
import os
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Keem\Desktop\projects\medguard_v1")
SERVICES_DIR = BASE_DIR / "medguard_app" / "services"

files_to_replace = [
    "treatment_validator.py",
    "interaction_checker.py",
    "side_effect_analyzer.py",
    "drug_alternatives.py",
]

print("=" * 60)
print("MEDGUARD SERVICE LAYER REFACTORING")
print("=" * 60)

for filename in files_to_replace:
    old_file = SERVICES_DIR / filename
    new_file = SERVICES_DIR / f"{filename.replace('.py', '_new.py')}"
    backup_file = SERVICES_DIR / f"{filename}.backup"
    
    if old_file.exists() and new_file.exists():
        print(f"\nProcessing {filename}...")
        
        shutil.copy2(old_file, backup_file)
        print(f"  ✓ Backed up to {backup_file.name}")
        
        shutil.copy2(new_file, old_file)
        print(f"  ✓ Replaced with new version")
        
        new_file.unlink()
        print(f"  ✓ Removed temporary _new.py file")
    else:
        print(f"\n⚠ Skipping {filename} - files not found")
        if not old_file.exists():
            print(f"    Missing: {old_file}")
        if not new_file.exists():
            print(f"    Missing: {new_file}")

print("\n" + "=" * 60)
print("REFACTORING COMPLETE!")
print("=" * 60)
print("\nBackup files created with .backup extension")
print("To revert: copy .backup files back to original names")
