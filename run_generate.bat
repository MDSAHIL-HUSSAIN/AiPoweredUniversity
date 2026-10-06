@echo off
cd /d "%~dp0"
if "%LLM_API_KEY%"=="" set /p LLM_API_KEY=Paste OpenAI API key and press Enter: 
if "%LLM_MODEL%"=="" set LLM_MODEL=gpt-4o-mini
python scripts\generate_students.py
python scripts\validate_data.py --dir data\synthetic --own --as-of 2026-10-06
python scripts\seed_test_db.py --students data\synthetic
python evaluations\run_tool_checks.py --db data\runtime\university.db --save ""
echo.
echo Done. Tell Claude.
pause
