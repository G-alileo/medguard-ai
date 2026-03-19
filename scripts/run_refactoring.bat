@echo off
echo ============================================================
echo MEDGUARD COMPLETE REFACTORING
echo ============================================================
echo.
echo This will:
echo   1. Replace service files with database-driven versions
echo   2. Remove all comments and emojis
echo   3. Create backups of all modified files
echo.
echo ============================================================
echo.

set /p confirm="Continue with refactoring? (yes/no): "
if /i not "%confirm%"=="yes" (
    echo Refactoring cancelled.
    pause
    exit /b
)

echo.
echo Starting refactoring...
echo.

python scripts\refactor_all.py

echo.
echo ============================================================
echo REFACTORING COMPLETE!
echo ============================================================
echo.
echo Next steps:
echo   1. Review the changes
echo   2. Run tests: python manage.py test
echo   3. Test the application manually
echo   4. If all looks good, delete .backup files
echo.
echo To rollback: Copy .backup files back to original names
echo.
pause
