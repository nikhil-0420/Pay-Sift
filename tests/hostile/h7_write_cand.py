# DANGEROUS: SANDBOX ONLY
# Hostile handler h7: attempts to write into /cand (read-only bind mount)
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Attempt to write or overwrite files in /cand
    with open("/cand/handler.py", "w") as f:
        f.write("# overwritten")
    return {"status": "applied", "reason": "overwrote cand"}
