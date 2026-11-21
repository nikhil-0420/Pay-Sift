#!/usr/bin/env bash
# PaySift Sandbox Runner (Bash Wrapper)
# Usage:
#   ./scripts/sandbox.sh --file <path_to_candidate.py> --mode <normal|restart|concurrency>
# Example:
#   ./scripts/sandbox.sh --file ref/handler_ref.py --mode normal

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
python3 -m runner.sandbox "$@"
