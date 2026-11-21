# DANGEROUS: SANDBOX ONLY
# Hostile handler h3: infinite loop
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

import time
from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Infinite CPU/wall-clock hang
    while True:
        time.sleep(0.1)
    return {"status": "applied", "reason": "loop finished"}
