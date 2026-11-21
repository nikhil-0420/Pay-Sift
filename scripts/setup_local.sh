#!/usr/bin/env bash
# PaySift Local Environment Setup (POSIX / Linux / macOS)
# Sets up Docker sandbox, python venv, dependencies, .env, and verifies selftest.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== PaySift Local Setup ==="

# 1. Check Docker
echo -e "\n[1/5] Checking Docker daemon..."
if docker info > /dev/null 2>&1; then
    echo "Docker is installed and running."
    echo "Building Docker sandbox image paysift-sandbox:1..."
    docker build -t paysift-sandbox:1 -f runner/Dockerfile .
    echo "Docker sandbox image built successfully."
else
    echo "WARNING: Docker is not running or not installed. Candidate sandbox execution will be unavailable."
fi

# 2. Virtual Environment and dependencies
echo -e "\n[2/5] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv || python -m venv .venv
    echo "Created .venv."
else
    echo ".venv already exists."
fi

if [ -f ".venv/bin/python" ]; then
    VENV_PYTHON=".venv/bin/python"
elif [ -f ".venv/Scripts/python.exe" ]; then
    VENV_PYTHON=".venv/Scripts/python.exe"
else
    VENV_PYTHON="python"
fi

echo "Installing dependencies from requirements.txt..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt
echo "Dependencies installed."

# 3. Environment configuration
echo -e "\n[3/5] Checking .env configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Copied .env.example to .env. Edit .env to add your API keys."
else
    echo ".env file already exists; leaving untouched."
fi

# 4. Self-test pipeline
echo -e "\n[4/5] Running PaySift self-test pipeline..."
set +e
"$VENV_PYTHON" cli.py selftest
SELFTEST_CODE=$?
set -e

# 5. Instructions
echo -e "\n[5/5] Setup completed!"
echo -e "\nTo start the PaySift backend API, run:"
echo "  python cli.py serve"
echo -e "\nTo start the PaySift frontend UI, run:"
echo "  cd ui"
echo "  npm install"
echo "  npm run dev"
echo ""

exit $SELFTEST_CODE
