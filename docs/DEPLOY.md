# PaySift Deployment & Operation Guide

PaySift supports two operational modes:
1. **Hosted Read-Only Mode (Render)**: Zero-setup cloud deployment serving benchmark results, kill matrix, evidence citations, and pre-computed repairs.
2. **Local Full Mode**: Interactive developer mode supporting live model generation, Docker sandboxed break execution, and live LLM repair loops.

---

## Live Deployments

- **Production Frontend (Vercel):** [https://pay-sift.vercel.app](https://pay-sift.vercel.app)
- **Production Backend (Render):** [https://paysift-api.onrender.com](https://paysift-api.onrender.com)
  - Health check: `https://paysift-api.onrender.com/health`
  - Runs endpoint: `https://paysift-api.onrender.com/runs`
  - Kill matrix: `https://paysift-api.onrender.com/kill-matrix`
- **Render Cold Starts Note:** Free-tier Render instances spin down after 15 minutes of inactivity. The initial wake request may take 45–55 seconds. The frontend automatically probes health and displays `"Backend waking or unavailable, showing static snapshot"` until the service is active, maintaining full read-only snapshot accessibility.

---

## Architecture Overview

```
                      +-----------------------------------+
                      |   Hosted Frontend (Vercel)        |
                      |    https://pay-sift.vercel.app    |
                      +-----------------+-----------------+
                                        |
                 +----------------------+----------------------+
                 | (Public Network)                            | (Private Network CORS)
                 v                                             v
+-----------------------------------+        +-----------------------------------+
|      Hosted Backend (Render)      |        |        Local Backend Daemon       |
|  https://paysift-api.onrender.com |        |       http://localhost:8000       |
+-----------------------------------+        +-----------------------------------+
| - Read-only benchmarks & runs     |        | - Full interactive repair loop    |
| - Pre-computed repairs            |        | - Live candidate break execution  |
| - You.com search proxy (rate-ltd) |        | - Docker sandbox isolation        |
| - Execution disabled (HTTP 403)   |        | - Local Gemini/Anthropic keys     |
+-----------------------------------+        +-----------------------------------+
```

---

## 1. Hosted Mode (Render Web Service)

### Service Configuration
The repository includes a ready-to-deploy `render.yaml` blueprint:
- **Service Type:** Web Service (`free` tier)
- **Runtime:** Python 3.12.9
- **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/health`
- **Root Directory:** Repository root (`.`)

### Environment Variables on Render
Configure these in the Render Dashboard (**Environment** tab):

| Variable | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `HOSTED_MODE` | `1` | Enables read-only protection, disabling Docker/model execution. |
| `PYTHON_VERSION` | `3.12.9` | Pins Python runtime version. |
| `CORS_ORIGINS` | `https://pay-sift.vercel.app` | Comma-separated list of allowed frontend origins. |
| `YDC_API_KEY` | *(Secret)* | You.com API key for live rule grounding searches. |
| `SEARCH_MAX_TOTAL` | `25` | Process-lifetime cap across all IPs on the hosted instance. |
| `SEARCH_MAX_PER_IP_PER_HOUR` | `10` | Sliding-window hourly cap per client IP. |

### Free-Tier Cold Starts (~50s)
Render free web services spin down after 15 minutes of inactivity. The first incoming request after idle will trigger a cold start taking approximately **45–55 seconds** while the container boots and installs dependencies. Subsequent requests execute in milliseconds. The frontend client includes retry logic and timeout allowances for this initial warmup.

### Why Execution & Sandbox Are Disabled on Render
1. **No Docker Daemon:** Render Web Services run inside lightweight container instances without access to a nested Docker daemon (`/var/run/docker.sock`).
2. **Untrusted Code Security:** Live candidate runs execute untrusted model code. Without rootless gVisor/Docker sandboxes, arbitrary code execution on a shared host is unsafe.
3. **API Key Isolation:** Live repairs consume LLM tokens. Hosted mode prevents public exhaustion of private API keys.

When a client sends `POST /break` or uncached `POST /repair` to a hosted backend, the server returns `403 Forbidden`:
```json
{
  "error": "disabled_in_hosted_mode",
  "message": "Needs Docker and your own model key. Clone the repo and run it locally."
}
```

Pre-computed repairs already cached in `repair/cache/*.json` remain fully readable via `POST /repair` with `200 OK`.

---

## 2. Local Mode (Full Interactive Setup)

To test live model generation, execute Docker-sandboxed breaks, and run interactive repair loops, run PaySift locally.

### Automated Setup

**On Windows (PowerShell):**
```powershell
.\scripts\setup_local.ps1
```

**On Linux / macOS (Bash):**
```bash
./scripts/setup_local.sh
```

These scripts verify Python >= 3.11, confirm Docker is running, create a virtual environment, install requirements, and scaffold `.env` from `.env.example`.

### Manual Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/PaySift.git
   cd PaySift
   ```

2. **Set up Python Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide your model and search keys:
   ```ini
   HOSTED_MODE=0
   GEMINI_API_KEY=your_gemini_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   YDC_API_KEY=your_youcom_key_here
   ```

4. **Verify Docker Daemon:**
   Ensure Docker Desktop or the Docker engine is running:
   ```bash
   docker info
   ```

5. **Start the Local Backend:**
   ```bash
   python cli.py serve
   # Or directly via uvicorn:
   uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```

6. **Start the Frontend UI:**
   ```bash
   cd ui
   npm install
   npm run dev
   ```

---

## 3. Connecting Hosted UI to Local Backend (Private Network CORS)

Users visiting the hosted production dashboard (`https://pay-sift.vercel.app`) can connect it directly to their local daemon (`http://localhost:8000` or `http://127.0.0.1:8000`) for zero-friction local execution.

### How Private-Network CORS Works
Modern browsers (Chrome, Edge, Safari) restrict public websites (`https://`) from accessing private networks (`localhost` / `127.0.0.1`) without explicit private-network preflight approval:
1. The browser sends an `OPTIONS` preflight request with header:
   ```http
   Access-Control-Request-Private-Network: true
   ```
2. The PaySift FastAPI backend recognizes this header and responds with:
   ```http
   Access-Control-Allow-Private-Network: true
   Access-Control-Allow-Origin: https://pay-sift.vercel.app
   ```
3. The browser permits the cross-origin request to proceed to the local daemon.

This allows users to keep their API keys and Docker environment safely on their own machines while using the hosted UI interface.
