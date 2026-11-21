# PaySift Candidate Generation Summary

- **Timestamp:** `2026-11-21T11:06:22.255716+00:00`
- **Total Planned Candidates:** `30`
- **Total Generated Candidates:** `15`
- **Compliant Candidates:** `15` (100% AST & intake compliant)
- **Non-Compliant Candidates:** `0`
- **API Calls Used:** `48 / 110` (10 calls reserved for repair; well within 120-call budget)
- **Dry Run:** `False`

## Model Configuration Status

| Model Name | Provider | Model ID | Status | Reason |
|---|---|---|---|---|
| `strong_a` | `google` | `gemini-3.5-flash-lite` | **USABLE** | Configured and ready; 10/10 candidates generated |
| `strong_b` | `openai_compatible` | `qwen/qwen3.8-27b` | **USABLE** | Configured and ready; 5/10 candidates generated (remaining rate-limited by Groq OTPM) |
| `strong_c` | `openai_compatible` | `inclusionai/ling-3.2-flash:free` | **USABLE** | Configured; 0/10 generated due to upstream 429 rate limiting on OpenRouter free pool |

## Generation Results by Model & Condition

| Model | Provider | Condition | Planned | Generated | Compliant | Non-Compliant | Regenerations | Notes |
|---|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` (`strong_a`) | `google` | `A` | 5 | 5 | 5 | 0 | 1 | All 5 samples generated and compliant |
| `gemini-3.5-flash-lite` (`strong_a`) | `google` | `B` | 5 | 5 | 5 | 0 | 0 | All 5 samples generated and compliant |
| `qwen/qwen3.8-27b` (`strong_b`) | `openai_compatible` (Groq) | `A` | 5 | 3 | 3 | 0 | 0 | Samples 1, 2, 4 compliant; 3 & 5 hit Groq 1000 OTPM limit |
| `qwen/qwen3.8-27b` (`strong_b`) | `openai_compatible` (Groq) | `B` | 5 | 2 | 2 | 0 | 0 | Samples 2, 3 compliant; 1, 4, 5 hit Groq 1000 OTPM limit |
| `inclusionai/ling-3.2-flash:free` (`strong_c`) | `openai_compatible` (OpenRouter) | `A` | 5 | 0 | 0 | 0 | 0 | Upstream 429 rate limit on free tier shared pool |
| `inclusionai/ling-3.2-flash:free` (`strong_c`) | `openai_compatible` (OpenRouter) | `B` | 5 | 0 | 0 | 0 | 0 | Upstream 429 rate limit on free tier shared pool |
| **Total** | | | **30** | **15** | **15** | **0** | **1** | **15 compliant candidates ready for pilot** |

## Generated Candidate Manifest

### strong_a (gemini-3.5-flash-lite)
- `candidates/strong_a/A/1.py` (Compliant, SHA256: `9fa39b8fd21c...`)
- `candidates/strong_a/A/2.py` (Compliant, SHA256: `5765912eb8b7...`)
- `candidates/strong_a/A/3.py` (Compliant, SHA256: `f19a0a811802...`)
- `candidates/strong_a/A/4.py` (Compliant, SHA256: `18f773663a8a...`)
- `candidates/strong_a/A/5.py` (Compliant, SHA256: `a937a0f4439c...`)
- `candidates/strong_a/B/1.py` (Compliant, SHA256: `955d5dc8ec70...`)
- `candidates/strong_a/B/2.py` (Compliant, SHA256: `fcbb206c60e3...`)
- `candidates/strong_a/B/3.py` (Compliant, SHA256: `879101ff6153...`)
- `candidates/strong_a/B/4.py` (Compliant, SHA256: `2b3f1737be74...`)
- `candidates/strong_a/B/5.py` (Compliant, SHA256: `89da262b9a10...`)

### strong_b (qwen/qwen3.8-27b)
- `candidates/strong_b/A/1.py` (Compliant, SHA256: `3b8e788bc57e...`)
- `candidates/strong_b/A/2.py` (Compliant, SHA256: `aa948c2c1c68...`)
- `candidates/strong_b/A/4.py` (Compliant, SHA256: `785d1e2eecfe...`)
- `candidates/strong_b/B/2.py` (Compliant, SHA256: `e828dcba84ca...`)
- `candidates/strong_b/B/3.py` (Compliant, SHA256: `cf21b5be8576...`)
