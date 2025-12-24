#!/bin/bash
# chmod + start.sh 
# Exit on error
set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored messages
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed, please install $1 first"
        exit 1
    fi
}

# Check required commands
check_command python3
check_command uv

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    print_error "Python 3.9 or higher is required, current version: $python_version"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    print_message "Creating virtual environment with uv..."
    uv venv .venv
else
    print_message "Virtual environment already exists, skipping creation..."
fi

# Install dependencies
print_message "Installing project dependencies..."
uv sync

# Activate virtual environment
print_message "Activating virtual environment..."
source .venv/bin/activate

# Check environment variables
if [ -f ".env" ]; then
    print_message "Found .env file, loading environment variables..."
fi

# Create logs directory
if [ ! -d "logs" ]; then
    mkdir -p logs
fi

# Start application
print_message "Starting application..."
print_message "Service will be available at http://localhost:9200"
print_message "Press Ctrl+C to stop the service"
print_message "Log file is saved at logs/app.log"

# Use tee command to output to both console and log file
uvicorn app.main:app --host 0.0.0.0 --port 9200 --reload --log-level debug --access-log 2>&1 | tee -a logs/app.log 