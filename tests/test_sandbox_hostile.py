"""Tests for Docker sandbox isolation against hostile handlers.

Guarded by Docker availability: skipped loudly if Docker daemon/CLI is missing.
Hostile handlers must NEVER be imported or executed natively.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import uuid
import pytest

from runner.sandbox import is_docker_available, is_docker_image_available, run_in_sandbox


DOCKER_READY = is_docker_available() and is_docker_image_available("paysift-sandbox:1")


@pytest.mark.skipif(not DOCKER_READY, reason="Docker or paysift-sandbox:1 image unavailable: Gate 4 BLOCKED")
class TestSandboxHostile:
    """Suite verifying containment of hostile handlers in Docker sandbox."""

    @pytest.fixture(autouse=True)
    def clean_containers_after_test(self):
        yield
        # Assert no leftover containers matching paysift-
        res = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=paysift-", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert res.stdout.strip() == "", f"Leftover containers found: {res.stdout.strip()}"

    def _run_hostile(self, hostile_filename: str) -> dict:
        hostile_file = Path(__file__).resolve().parent / "hostile" / hostile_filename
        job = {
            "candidate_file": str(hostile_file),
            "mode": "normal",
            "sequences": [{
                "seed": 0,
                "steps": [{
                    "raw_body_b64": "e30=",
                    "signature": "00" * 32,
                    "tag": "hostile_test",
                }],
            }],
        }
        return run_in_sandbox(hostile_file, job, mode="normal", timeout=35.0)

    def test_h1_socket_contained(self):
        """Hostile h1 attempts outbound socket connection."""
        res = self._run_hostile("h1_socket.py")
        assert res["ok"] is True
        results = res["results"]
        # Should be contained (socket error or network unreachable)
        step_resp = results[0]["steps"][0]["response"]
        assert "error" in step_resp or step_resp.get("status") != "applied"

    def test_h2_write_root_contained(self):
        """Hostile h2 attempts write to read-only root and /runner."""
        res = self._run_hostile("h2_write_root.py")
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        assert "error" in step_resp or "Read-only file system" in str(step_resp)

    def test_h3_infinite_loop_timeout_contained(self):
        """Hostile h3 hangs in infinite loop."""
        res = self._run_hostile("h3_infinite_loop.py")
        # Per-step timeout (5s) intercepts hang
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        assert step_resp == "timeout"

    def test_h4_alloc_2gb_oom_contained(self):
        """Hostile h4 attempts 2GB RAM allocation with 256m container memory limit."""
        res = self._run_hostile("h4_alloc_2gb.py")
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        assert "error" in step_resp or "MemoryError" in str(step_resp)

    def test_h5_forkbomb_pids_limit_contained(self):
        """Hostile h5 attempts forkbomb with 128 pids-limit."""
        res = self._run_hostile("h5_forkbomb.py")
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        assert "error" in step_resp or "BlockingIOError" in str(step_resp) or "Resource temporarily unavailable" in str(step_resp)

    def test_h6_environ_canary_isolation(self, monkeypatch):
        """Hostile h6 tries to read host secrets / environ; asserts canary variable never leaks."""
        canary_secret = f"CANARY_SECRET_{uuid.uuid4().hex}"
        monkeypatch.setenv("PAYSIFT_CANARY", canary_secret)

        res = self._run_hostile("h6_read_proc_environ_home.py")
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        resp_text = str(step_resp)
        assert canary_secret not in resp_text, "Host environment variable leaked into container!"

    def test_h7_write_cand_contained(self):
        """Hostile h7 attempts write into read-only bind-mounted /cand."""
        res = self._run_hostile("h7_write_cand.py")
        assert res["ok"] is True
        step_resp = res["results"][0]["steps"][0]["response"]
        assert "error" in step_resp or "Read-only file system" in str(step_resp)
