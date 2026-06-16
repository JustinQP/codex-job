@echo off
setlocal

cd /d "%~dp0.."

if not exist data mkdir data

set MODE=%~1
if "%MODE%"=="" set MODE=all

if /I "%MODE%"=="api" goto start_api
if /I "%MODE%"=="runner" goto start_runner
if /I "%MODE%"=="runner-once" goto start_runner_once
if /I "%MODE%"=="all" goto start_all

echo Usage:
echo   scripts\start.bat
echo   scripts\start.bat api
echo   scripts\start.bat runner
echo   scripts\start.bat runner-once
exit /b 1

:start_all
call :open_api
call :open_runner
echo.
echo API docs: http://127.0.0.1:8000/docs
exit /b 0

:start_api
call :open_api
echo.
echo API docs: http://127.0.0.1:8000/docs
exit /b 0

:start_runner
call :open_runner
exit /b 0

:start_runner_once
start "codex-runner-once" /D "%CD%" cmd /k "python runner\runner.py --once"
exit /b 0

:open_api
start "codex-runner-api" /D "%CD%" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
exit /b 0

:open_runner
start "codex-runner-worker" /D "%CD%" cmd /k "python runner\runner.py"
exit /b 0
