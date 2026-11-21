# DANGEROUS: SANDBOX ONLY
# Hostile handler h1: opens a socket to an external IP
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

import socket
from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Attempt to open an outbound network socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(("8.8.8.8", 53))
    return {"status": "applied", "reason": "socket connected"}
