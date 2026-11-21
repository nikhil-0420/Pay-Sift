"""LLM provider adapters for candidate generation with secret scrubbing and retry logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

import httpx


def load_env_file(env_path: Optional[Path] = None) -> None:
    """Load key-value pairs from .env file into os.environ if not already set."""
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return

    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val


def scrub_secrets(text: str, secret_keys: Optional[List[str]] = None) -> str:
    """Scrub sensitive API keys and tokens from logs and error strings."""
    if not text:
        return text

    if secret_keys is None:
        secret_keys = []
        for env_var in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "SMALL_MODEL_API_KEY",
            "YDC_API_KEY",
        ]:
            val = os.environ.get(env_var, "").strip()
            if len(val) >= 6:
                secret_keys.append(val)

    scrubbed = str(text)
    for key in secret_keys:
        if key and len(key) >= 6 and key in scrubbed:
            scrubbed = scrubbed.replace(key, "[REDACTED_API_KEY]")
    return scrubbed


@dataclass
class GenerationResult:
    """Outcome of a single generation request including all attempt metadata."""

    raw_text: str
    model_id: str
    provider: str
    temperature: Optional[float]
    max_tokens: int
    token_usage: Dict[str, int]
    latency: float
    timestamp: str
    attempts: List[Dict[str, Any]] = field(default_factory=list)


class ProviderAdapter:
    """Base provider adapter."""

    provider_name: str = "base"

    def generate(
        self,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> GenerationResult:
        raise NotImplementedError


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic Messages API."""

    provider_name: str = "anthropic"

    def generate(
        self,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> GenerationResult:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        attempts: List[Dict[str, Any]] = []
        raw_text = ""
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0.0

        for attempt_idx in range(1, 4):
            t0 = time.monotonic()
            ts = datetime.now(timezone.utc).isoformat()
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    latency = time.monotonic() - t0
                    total_latency += latency

                    if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                        err_msg = scrub_secrets(resp.text, [api_key])
                        attempts.append({
                            "attempt": attempt_idx,
                            "timestamp": ts,
                            "status": resp.status_code,
                            "latency": latency,
                            "error": err_msg,
                        })
                        if attempt_idx < 3:
                            time.sleep(2.0 ** (attempt_idx - 1))
                            continue
                        raise RuntimeError(f"Anthropic API error HTTP {resp.status_code}: {err_msg}")

                    resp.raise_for_status()
                    data = resp.json()
                    raw_text = data["content"][0]["text"]
                    usage = data.get("usage", {})
                    token_usage = {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    }
                    attempts.append({
                        "attempt": attempt_idx,
                        "timestamp": ts,
                        "status": resp.status_code,
                        "latency": latency,
                        "token_usage": token_usage,
                    })
                    break
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                latency = time.monotonic() - t0
                total_latency += latency
                err_msg = scrub_secrets(str(exc), [api_key])
                attempts.append({
                    "attempt": attempt_idx,
                    "timestamp": ts,
                    "latency": latency,
                    "error": err_msg,
                })
                if attempt_idx < 3:
                    time.sleep(2.0 ** (attempt_idx - 1))
                    continue
                raise RuntimeError(f"Anthropic network error: {err_msg}")

        return GenerationResult(
            raw_text=raw_text,
            model_id=model_id,
            provider=self.provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            token_usage=token_usage,
            latency=total_latency,
            timestamp=datetime.now(timezone.utc).isoformat(),
            attempts=attempts,
        )


class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI Chat Completions API."""

    provider_name: str = "openai"

    def generate(
        self,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> GenerationResult:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        endpoint = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        attempts: List[Dict[str, Any]] = []
        raw_text = ""
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0.0

        for attempt_idx in range(1, 4):
            t0 = time.monotonic()
            ts = datetime.now(timezone.utc).isoformat()
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)
                    latency = time.monotonic() - t0
                    total_latency += latency

                    if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                        err_msg = scrub_secrets(resp.text, [api_key])
                        attempts.append({
                            "attempt": attempt_idx,
                            "timestamp": ts,
                            "status": resp.status_code,
                            "latency": latency,
                            "error": err_msg,
                        })
                        if attempt_idx < 3:
                            time.sleep(2.0 ** (attempt_idx - 1))
                            continue
                        raise RuntimeError(f"OpenAI API error HTTP {resp.status_code}: {err_msg}")

                    resp.raise_for_status()
                    data = resp.json()
                    raw_text = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    token_usage = {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    attempts.append({
                        "attempt": attempt_idx,
                        "timestamp": ts,
                        "status": resp.status_code,
                        "latency": latency,
                        "token_usage": token_usage,
                    })
                    break
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                latency = time.monotonic() - t0
                total_latency += latency
                err_msg = scrub_secrets(str(exc), [api_key])
                attempts.append({
                    "attempt": attempt_idx,
                    "timestamp": ts,
                    "latency": latency,
                    "error": err_msg,
                })
                if attempt_idx < 3:
                    time.sleep(2.0 ** (attempt_idx - 1))
                    continue
                raise RuntimeError(f"OpenAI network error: {err_msg}")

        return GenerationResult(
            raw_text=raw_text,
            model_id=model_id,
            provider=self.provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            token_usage=token_usage,
            latency=total_latency,
            timestamp=datetime.now(timezone.utc).isoformat(),
            attempts=attempts,
        )


class GoogleAdapter(ProviderAdapter):
    """Adapter for Google Gemini generateContent API."""

    provider_name: str = "google"

    def generate(
        self,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> GenerationResult:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        headers = {"content-type": "application/json"}
        gen_config: Dict[str, Any] = {"maxOutputTokens": max_tokens}
        if temperature is not None:
            gen_config["temperature"] = temperature

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }

        attempts: List[Dict[str, Any]] = []
        raw_text = ""
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_latency = 0.0

        for attempt_idx in range(1, 4):
            t0 = time.monotonic()
            ts = datetime.now(timezone.utc).isoformat()
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    latency = time.monotonic() - t0
                    total_latency += latency

                    if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                        err_msg = scrub_secrets(resp.text, [api_key])
                        attempts.append({
                            "attempt": attempt_idx,
                            "timestamp": ts,
                            "status": resp.status_code,
                            "latency": latency,
                            "error": err_msg,
                        })
                        if attempt_idx < 3:
                            time.sleep(2.0 ** (attempt_idx - 1))
                            continue
                        raise RuntimeError(f"Google API error HTTP {resp.status_code}: {err_msg}")

                    resp.raise_for_status()
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    usage = data.get("usageMetadata", {})
                    token_usage = {
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                        "total_tokens": usage.get("totalTokenCount", 0),
                    }
                    attempts.append({
                        "attempt": attempt_idx,
                        "timestamp": ts,
                        "status": resp.status_code,
                        "latency": latency,
                        "token_usage": token_usage,
                    })
                    break
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                latency = time.monotonic() - t0
                total_latency += latency
                err_msg = scrub_secrets(str(exc), [api_key])
                attempts.append({
                    "attempt": attempt_idx,
                    "timestamp": ts,
                    "latency": latency,
                    "error": err_msg,
                })
                if attempt_idx < 3:
                    time.sleep(2.0 ** (attempt_idx - 1))
                    continue
                raise RuntimeError(f"Google network error: {err_msg}")

        return GenerationResult(
            raw_text=raw_text,
            model_id=model_id,
            provider=self.provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            token_usage=token_usage,
            latency=total_latency,
            timestamp=datetime.now(timezone.utc).isoformat(),
            attempts=attempts,
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    """Adapter for OpenAI-compatible endpoints."""

    provider_name: str = "openai_compatible"


class FakeProviderAdapter(ProviderAdapter):
    """Mock provider adapter for offline tests and simulated candidate generation."""

    provider_name: str = "fake"

    def __init__(self, canned_responses: Optional[List[str]] = None, fail_attempts: int = 0) -> None:
        self.canned_responses = canned_responses or [
            "```python\nimport sqlite3\ndef handle_event(db_path, raw_body, signature, secret):\n    return {'status': 'applied'}\n```"
        ]
        self.fail_attempts = fail_attempts
        self.call_count = 0

    def generate(
        self,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> GenerationResult:
        self.call_count += 1
        t0 = time.monotonic()
        ts = datetime.now(timezone.utc).isoformat()

        if self.call_count <= self.fail_attempts:
            raise RuntimeError(f"Simulated API rate limit error (key: {api_key or 'no-key'})")

        idx = (self.call_count - self.fail_attempts - 1) % len(self.canned_responses)
        raw_text = self.canned_responses[idx]

        return GenerationResult(
            raw_text=raw_text,
            model_id=model_id,
            provider=self.provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
            token_usage={"prompt_tokens": len(prompt) // 4, "completion_tokens": len(raw_text) // 4, "total_tokens": (len(prompt) + len(raw_text)) // 4},
            latency=time.monotonic() - t0,
            timestamp=ts,
            attempts=[{"attempt": 1, "timestamp": ts, "status": 200, "latency": 0.001}],
        )


PROVIDERS: Dict[str, ProviderAdapter] = {
    "anthropic": AnthropicAdapter(),
    "openai": OpenAIAdapter(),
    "google": GoogleAdapter(),
    "openai_compatible": OpenAICompatibleAdapter(),
    "fake": FakeProviderAdapter(),
}


def get_provider(provider_name: str) -> ProviderAdapter:
    """Lookup provider adapter by name."""
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[provider_name]
