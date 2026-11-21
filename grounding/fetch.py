"""Fetch evidence from You.com and cache raw responses and parsed sources per rule."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from grounding.youcom import YouComClient


CACHE_DIR = Path("grounding/cache")
QUERIES_FILE = Path("grounding/queries.yaml")


def load_queries(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load query definitions and rule hashes from queries.yaml."""
    file_path = path or QUERIES_FILE
    if not file_path.is_file():
        raise FileNotFoundError(f"Queries file not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_web_snippets(web_item: Dict[str, Any], max_len: int = 350) -> str:
    """Extract a concise excerpt from search result snippets or description."""
    snippets = web_item.get("snippets") or []
    if snippets:
        text = " ".join(s.strip() for s in snippets if s.strip())
    else:
        text = web_item.get("description", "").strip()

    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def fetch_rule_evidence(
    client: YouComClient,
    rule_id: str,
    rule_spec: Dict[str, Any],
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> Dict[str, Any]:
    """Fetch and cache search evidence for a single rule."""
    cache_file = cache_dir / f"{rule_id}.json"
    if cache_file.is_file() and not refresh:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    cache_dir.mkdir(parents=True, exist_ok=True)
    queries = rule_spec.get("queries", [])
    raw_responses: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    seen_urls = set()

    for query in queries:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            resp = client.search(query=query, count=3)
        except Exception as exc:
            # Record failure in raw_responses if error
            raw_responses.append({
                "query": query,
                "error": str(exc),
                "timestamp": now_iso,
            })
            continue

        raw_responses.append({
            "query": query,
            "response": resp,
            "timestamp": now_iso,
        })

        web_results = resp.get("results", {}).get("web", [])
        for rank, item in enumerate(web_results, 1):
            url = item.get("url", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            source_id = f"{rule_id}_s{len(sources) + 1}"
            snippet = parse_web_snippets(item)
            sources.append({
                "id": source_id,
                "url": url,
                "title": item.get("title", "").strip() or "Untitled",
                "snippet": snippet,
                "rank": rank,
                "query": query,
                "retrieved_at": now_iso,
                "provider": "you.com",
            })

    cache_data = {
        "rule_id": rule_id,
        "title": rule_spec.get("title", ""),
        "description": rule_spec.get("description", ""),
        "text_hash": rule_spec.get("text_hash", ""),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "raw_responses": raw_responses,
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)

    return cache_data


def fetch_all_evidence(
    client: Optional[YouComClient] = None,
    rules: Optional[List[str]] = None,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
    queries_file: Path = QUERIES_FILE,
) -> Dict[str, Any]:
    """Fetch evidence for specified or all rules."""
    client = client or YouComClient()
    queries_data = load_queries(queries_file)
    all_rules = queries_data.get("rules", {})

    target_rule_ids = rules or sorted(all_rules.keys(), key=lambda r: int(r[1:]))
    results: Dict[str, Any] = {}

    for rule_id in target_rule_ids:
        if rule_id not in all_rules:
            continue
        rule_spec = all_rules[rule_id]
        cache_data = fetch_rule_evidence(
            client=client,
            rule_id=rule_id,
            rule_spec=rule_spec,
            cache_dir=cache_dir,
            refresh=refresh,
        )
        results[rule_id] = cache_data

    return results
