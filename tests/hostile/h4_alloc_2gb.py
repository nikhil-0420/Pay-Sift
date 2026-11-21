# DANGEROUS: SANDBOX ONLY
# Hostile handler h4: allocates 2GB memory
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Attempt to allocate 2 GB of memory (container limit is 256m)
    big_block = bytearray(2 * 1024 * 1024 * 1024)
    return {"status": "applied", "reason": f"allocated {len(big_block)} bytes"}
