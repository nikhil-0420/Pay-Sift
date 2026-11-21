# You.com Web Search API Technical Notes

## 1. Endpoints & Methods

- **Primary Production Search Endpoint**:
  - `POST https://ydc-index.io/v1/search`
  - Recommended by OpenAPI spec (`openapi/web-search.json`) and documentation guides.
  - Supports structured JSON request body with domain filtering, snippet extraction, and count parameters.
- **Legacy / GET Search Endpoint**:
  - `GET https://api.you.com/v1/search` (also `GET https://ydc-index.io/v1/search`)
  - Parameters passed as query parameters (`?query=...&count=...`). Deprecated for new features, but functional.
- **Keyless Fallback Endpoint**:
  - `POST https://api.you.com/v1/agents/search`
  - Agent-oriented endpoint accepting machine payments or unauthenticated requests with unverified rate limits. Used strictly as an opt-in fallback in PaySift (`--allow-keyless`).

## 2. Authentication

- Header: `X-API-Key: <YDC_API_KEY>`
- Loaded strictly from `.env` or process environment. Never logged, printed, or committed.
- Error codes on auth failure: `401 Unauthorized` (invalid or missing key on authenticated endpoints).

## 3. Request Fields

JSON body for `POST https://ydc-index.io/v1/search`:
- `query` (string, required): Search query string. Supports search operators (`site:`, `AND`, `OR`, etc.).
- `count` (integer, optional, default: 10, max: 100): Number of results requested. PaySift uses `count=3` or `5` for concise, deterministic evidence retrieval.
- `safesearch` (string, optional): `"moderate"` (default), `"off"`, or `"strict"`.
- `freshness` (string, optional): Freshness filter (e.g., `"month"`, `"year"`).
- Optional domain filters: `include_domains` (list of strings).

## 4. Response Fields Used in PaySift

The API returns a root object containing `results.web`:
```json
{
  "results": {
    "web": [
      {
        "url": "https://docs.stripe.com/webhooks/signature",
        "title": "Manage webhook endpoints | Stripe Documentation",
        "description": "...",
        "snippets": [
          "Verify signatures using the raw request body...",
          "..."
        ],
        "page_age": "2025-11-15T10:30:00"
      }
    ]
  },
  "metadata": {
    "search_uuid": "...",
    "query": "...",
    "latency": 0.34
  }
}
```

PaySift parses and retains only the fields needed for grounding:
- `url`: Canonical source URL.
- `title`: Page or article title.
- `snippet`: Joined or selected excerpt from `snippets` (short excerpts, capped, no full HTML/markdown).
- `rank`: 1-based index in search results.
- `query`: Query that retrieved the result.
- `retrieved_at`: UTC ISO-8601 retrieval timestamp.
- `provider`: `"you.com"`.

## 5. Rate Limits & Error Codes

- `200 OK`: Successful search with results.
- `401 Unauthorized`: Missing or invalid `X-API-Key`.
- `402 Payment Required`: Out of credits on paid tier.
- `422 Unprocessable Entity`: Invalid request parameters.
- `429 Too Many Requests`: Rate limit exceeded. Handled with exponential backoff (at most 2 retries).
- `500 / 503 Server Error`: Upstream failure. Handled with backoff and retry.
- Global Call Cap: PaySift enforces a client-side hard cap (default: 60 calls) to prevent accidental quota exhaustion.

## 6. Deviations from Initial Plan

1. **Host and Path**: The plan referenced both `api.you.com` and `ydc-index.io`. Documentation and OpenAPI confirm `https://ydc-index.io/v1/search` is the official, preferred production endpoint for web search, while `api.you.com/v1/agents/search` is keyless/agent-only.
2. **Text Extraction**: Highlights and full-page crawl require additional parameters (`extraction: {extraction_mode: "highlights"}`) and incur separate pricing/latency. For PaySift's evidence layer, the default `snippets` array provides exact, high-relevance quotes without extra latency or crawling overhead.
3. **Spec Authority**: The OpenAPI schema (`https://you.com/docs/openapi/web-search.json`) and live tests verify that `POST /v1/search` with `{query, count}` returns unified `results.web` with snippets.

## 7. Verification Summary

Live endpoint tests conducted on 2026-11-21:
- `POST https://ydc-index.io/v1/search`: HTTP 200, returned 3 web results with snippets.
- `GET https://api.you.com/v1/search`: HTTP 200, returned 3 web results.
- `POST https://api.you.com/v1/agents/search` (keyless fallback): HTTP 200, verified working.
