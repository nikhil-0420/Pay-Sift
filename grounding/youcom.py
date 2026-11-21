"""You.com API client with call capping, retries, and secret scrubbing."""

from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import httpx

from generate.providers import load_env_file, scrub_secrets

PRIMARY_ENDPOINT = "https://ydc-index.io/v1/search"
KEYLESS_ENDPOINT = "https://api.you.com/v1/agents/search"
DEFAULT_CALL_CAP = 60
DEFAULT_TIMEOUT_SECS = 10.0
MAX_RETRIES = 2


class YouComClient:
    """Client for querying the You.com search APIs with rate limits and quota caps."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        call_cap: int = DEFAULT_CALL_CAP,
        timeout: float = DEFAULT_TIMEOUT_SECS,
        allow_keyless: bool = False,
        env_path: Optional[Path] = None,
    ) -> None:
        load_env_file(env_path)
        self.api_key = api_key or os.environ.get("YDC_API_KEY", "").strip()
        self.call_cap = call_cap
        self.timeout = timeout
        self.allow_keyless = allow_keyless
        self.calls_used = 0

    def search(
        self,
        query: str,
        count: int = 5,
        allow_keyless: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Perform a web search query through You.com with retry and error scrubbing."""
        use_keyless = self.allow_keyless if allow_keyless is None else allow_keyless

        if not self.api_key and not use_keyless:
            raise ValueError(
                "YDC_API_KEY is missing and keyless fallback is disabled (allow_keyless=False)."
            )

        if self.calls_used >= self.call_cap:
            raise RuntimeError(
                f"You.com API call cap reached: {self.calls_used}/{self.call_cap} calls used."
            )

        endpoint = PRIMARY_ENDPOINT if self.api_key else KEYLESS_ENDPOINT
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        payload = {"query": query, "count": count}

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                self.calls_used += 1
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)

                if resp.status_code == 200:
                    return resp.json()

                # Retry on 429 or 5xx
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    time.sleep(0.5 * (2 ** attempt))
                    continue

                scrubbed_resp = scrub_secrets(resp.text, [self.api_key])
                raise RuntimeError(
                    f"You.com request failed with status {resp.status_code}: {scrubbed_resp}"
                )
            except Exception as exc:
                last_error = exc
                if attempt < MAX_RETRIES and isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break

        scrubbed_err = scrub_secrets(str(last_error), [self.api_key])
        raise RuntimeError(f"You.com API call failed: {scrubbed_err}") from None
