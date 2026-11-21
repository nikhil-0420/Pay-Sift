"""Ground-truth pure-Python contract model.

Simulates state transitions according to Rules R0-R10 and Clarifications C1-C9.
Never imports candidate code.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple


class Model:
    """Pure-Python model tracking financial ground truth and expected status/rules."""

    def __init__(self) -> None:
        # payment_id -> {"cap": int, "ref": int, "n_cap": int, "n_ref": int}
        self.pay: Dict[str, Dict[str, int]] = {}
        # Set of event_ids that have transitioned to "applied"
        self.applied: Set[str] = set()
        # Set of event_ids that encountered a rejection (R1, R2, R4, R5, R6)
        self.rejected_ids: Set[str] = set()
        # Full ledger history
        self.ledger: List[Dict[str, Any]] = []

    def apply(
        self,
        raw_body: bytes,
        sig_ok: bool,
        payload_ok: bool,
        parsed: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Process an event according to strict check precedence (C3).

        Returns:
            (status, rule) where status is in {"applied", "duplicate", "rejected"}.
        """
        # Best-effort extraction of event_id on failure paths for R8 tracking
        eid: Optional[str] = None
        if parsed and isinstance(parsed.get("event_id"), str) and parsed.get("event_id"):
            eid = parsed["event_id"]
        else:
            try:
                data = json.loads(bytes(raw_body).decode("utf-8"))
                if isinstance(data, dict) and isinstance(data.get("event_id"), str) and data.get("event_id"):
                    eid = data["event_id"]
            except Exception:
                pass

        # 1. Signature Check (R1)
        if not sig_ok:
            if eid:
                self.rejected_ids.add(eid)
            return "rejected", "R1"

        # 2. Payload Validation (R2)
        if not payload_ok or parsed is None:
            if eid:
                self.rejected_ids.add(eid)
            return "rejected", "R2"

        eid = parsed["event_id"]
        pid = parsed["payment_id"]
        ev_type = parsed["type"]
        amount = parsed["amount_paise"]

        # 3. Duplicate / Idempotency Check (R3)
        if eid in self.applied:
            return "duplicate", "R3"

        # 4. Business Logic: Payment Capture (R4)
        if ev_type == "payment.captured":
            if pid in self.pay:
                self.rejected_ids.add(eid)
                return "rejected", "R4"

            self.pay[pid] = {
                "cap": amount,
                "ref": 0,
                "n_cap": 1,
                "n_ref": 0,
            }
            self.ledger.append({
                "payment_id": pid,
                "kind": "capture",
                "amount_paise": amount,
                "event_id": eid,
            })
            rule = "R8" if eid in self.rejected_ids else "R4"
            self.applied.add(eid)
            return "applied", rule

        # 5. Business Logic: Refund Processed (R5, R6)
        elif ev_type == "refund.processed":
            p = self.pay.get(pid)
            if not p:
                self.rejected_ids.add(eid)
                return "rejected", "R5"

            if p["ref"] + amount > p["cap"]:
                self.rejected_ids.add(eid)
                return "rejected", "R6"

            p["ref"] += amount
            p["n_ref"] += 1
            self.ledger.append({
                "payment_id": pid,
                "kind": "refund",
                "amount_paise": amount,
                "event_id": eid,
            })
            rule = "R8" if eid in self.rejected_ids else "R6"
            self.applied.add(eid)
            return "applied", rule

        else:
            if eid:
                self.rejected_ids.add(eid)
            return "rejected", "R2"

    def get_snapshot(self) -> Dict[str, Any]:
        """Return ground truth state snapshot."""
        payments_rows = []
        for pid, d in sorted(self.pay.items()):
            payments_rows.append({
                "payment_id": pid,
                "captured_paise": d["cap"],
                "refunded_paise": d["ref"],
            })

        summary: Dict[str, Dict[str, int]] = {}
        for entry in self.ledger:
            pid = entry["payment_id"]
            if pid not in summary:
                summary[pid] = {
                    "captures_count": 0,
                    "captures_sum": 0,
                    "refunds_count": 0,
                    "refunds_sum": 0,
                }
            if entry["kind"] == "capture":
                summary[pid]["captures_count"] += 1
                summary[pid]["captures_sum"] += entry["amount_paise"]
            elif entry["kind"] == "refund":
                summary[pid]["refunds_count"] += 1
                summary[pid]["refunds_sum"] += entry["amount_paise"]

        return {
            "payments": payments_rows,
            "ledger": list(self.ledger),
            "summary": summary,
        }
