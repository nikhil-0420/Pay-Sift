# DANGEROUS: SANDBOX ONLY
# Hostile handler h5: fork bomb
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Attempt to exhaust process limit (pids-limit is 128)
    while True:
        try:
            os.fork()
        except Exception:
            break
    return {"status": "applied", "reason": "forked"}
