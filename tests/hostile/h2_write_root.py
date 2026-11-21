# DANGEROUS: SANDBOX ONLY
# Hostile handler h2: attempts to write to / and /runner
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Attempt to write to root filesystem
    with open("/hacked.txt", "w") as f:
        f.write("malicious write")
    with open("/runner/hacked.txt", "w") as f:
        f.write("malicious write")
    return {"status": "applied", "reason": "wrote to root"}
