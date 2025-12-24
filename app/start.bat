@echo off
setlocal enabledelayedexpansion

:: Color codes
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

:: Print colored message
call :print_message "Checking environment..."

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Python is not installed, please install Python first
    pause
    exit /b 1
)

:: Check if uv is installed
uv --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% uv is not installed, please install uv first
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
set REQUIRED_VERSION=3.11

:: Version comparison
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if !MAJOR! LSS 3 (
    echo %RED%[ERROR]%NC% Python 3.11 or higher is required, current version: !PYTHON_VERSION!
    pause
    exit /b 1
) else if !MAJOR! EQU 3 (
    if !MINOR! LSS 11 (
        echo %RED%[ERROR]%NC% Python 3.11 or higher is required, current version: !PYTHON_VERSION!
        pause
        exit /b 1
    )
)

:: Check if virtual environment exists
if not exist ".venv" (
    echo %GREEN%[INFO]%NC% Creating virtual environment with uv...
    uv venv .venv
    if errorlevel 1 (
        echo %RED%[ERROR]%NC% Failed to create virtual environment
        pause
        exit /b 1
    )
) else (
    echo %GREEN%[INFO]%NC% Virtual environment already exists, skipping creation...
)

:: Install dependencies
echo %GREEN%[INFO]%NC% Installing project dependencies...
uv sync
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to install dependencies
    pause
    exit /b 1
)

:: Activate virtual environment
echo %GREEN%[INFO]%NC% Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to activate virtual environment
    pause
    exit /b 1
)

:: Check environment variables file
if exist ".env" (
    echo %GREEN%[INFO]%NC% Found .env file, loading environment variables...
)

:: Create logs directory
if not exist "logs" (
    mkdir logs
)

:: Start application
echo %GREEN%[INFO]%NC% Starting application...
echo %GREEN%[INFO]%NC% Service will be available at http://localhost:9200
echo %GREEN%[INFO]%NC% Press Ctrl+C to stop the service
echo %GREEN%[INFO]%NC% Log file is saved at logs\app.log

:: Start uvicorn with proper output handling using PowerShell
powershell -Command "uvicorn app.main:app --host 0.0.0.0 --port 9200 --reload --log-level debug --access-log --use-colors 2>&1 | Tee-Object -FilePath 'logs\app.log'"

exit /b 0

:print_message
echo %GREEN%[INFO]%NC% %~1
exit /b 0 