#!/bin/bash
# Usage: source shell_venv.sh
# Do not run directly with ./shell_venv.sh
# Exit on error
set -e

# Check if command exists
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed, please install uv first"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with uv..."
    uv venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing project dependencies..."
uv sync 