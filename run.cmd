@echo off
setlocal
cd /d "%~dp0"
echo HireLoop - http://127.0.0.1:8000
echo Gardez cette fenetre ouverte. Ctrl+C pour arreter.
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 server.py
    goto end
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
    goto end
)
python server.py
:end
pause
