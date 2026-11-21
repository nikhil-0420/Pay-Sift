# PaySift

Finds the smallest event sequence that breaks AI-written payment webhook handlers. Seeded attacks, restarts and concurrent deliveries, a ledger oracle, a delta-debugging shrinker, a repair loop, and a kill matrix that proves the harness.

## Quickstart

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# On Windows PowerShell: .venv\Scripts\Activate.ps1
# On Linux/macOS: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run self-test suite
python cli.py selftest

# 4. Run the interactive demo
python cli.py demo
```

## Status

The harness is built and verified against 13 hand-written mutants; the sandbox gate and live model pilot are pending, so no model has been tested yet.

## Documentation & Plans

- [Build Plan v3](PAYSIFT_BUILD_PLAN_v3.md)
- [Demo Walkthrough](README_DEMO.md)
- [Morning Handoff](MORNING_HANDOFF.md)
