"""Child process runner executing candidate handler events line-by-line.

Invoked by runner/worker.py in a dedicated subprocess per sequence (normal mode)
or per call (restart mode).
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict


def load_candidate_handler(candidate_file: Path):
    """Dynamically import handle_event from staged candidate file."""
    if not candidate_file.is_file():
        raise FileNotFoundError(f"Candidate file not found: {candidate_file}")

    spec = importlib.util.spec_from_file_location("candidate_module", str(candidate_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {candidate_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["candidate_module"] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "handle_event"):
        raise AttributeError(f"Candidate {candidate_file} does not define handle_event()")

    return getattr(module, "handle_event")


def main() -> int:
    parser = argparse.ArgumentParser(description="PaySift Child Runner")
    parser.add_argument("--candidate", required=True, help="Path to staged candidate handler.py")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--secret", required=True, help="Webhook signing secret")
    args = parser.parse_args()

    candidate_path = Path(args.candidate).resolve()
    db_path = str(Path(args.db).resolve())
    secret = args.secret

    try:
        handle_event_fn = load_candidate_handler(candidate_path)
    except Exception as exc:
        # If module fails to load or import, emit error for each step
        for line in sys.stdin:
            print(json.dumps({"error": f"Candidate import failed: {exc}"}), flush=True)
        return 1

    # Read steps from stdin line by line
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            step_data = json.loads(line)
            raw_b64 = step_data["raw_body_b64"]
            signature = step_data["signature"]
            raw_body = base64.b64decode(raw_b64.encode("ascii"))

            # Call candidate handler
            result = handle_event_fn(db_path, raw_body, signature, secret)
            print(json.dumps(result), flush=True)
        except Exception as exc:
            print(json.dumps({"error": f"Exception in handle_event: {exc}"}), flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
