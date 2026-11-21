import { normalizeGrounding, type GroundingData } from "./grounding";

export type AnyRecord = Record<string, any>;

export interface DataSource {
  health(signal?: AbortSignal): Promise<AnyRecord>;
  listRuns(signal?: AbortSignal): Promise<AnyRecord[]>;
  getRun(id: string, signal?: AbortSignal): Promise<AnyRecord>;
  getKillMatrix(signal?: AbortSignal): Promise<AnyRecord>;
  breakIt(
    candidateId: string,
    scenario: string,
    signal?: AbortSignal,
  ): Promise<AnyRecord>;
  repair(
    candidateId: string,
    failureId: number,
    signal?: AbortSignal,
  ): Promise<AnyRecord>;
  getScenarioVerdicts(): Promise<AnyRecord>;
  getSpec(): Promise<string>;
  getSpecHash(): Promise<string>;
  getStatus(): Promise<AnyRecord>;
  getPilotReport(): Promise<string>;
  getEvidence(signal?: AbortSignal): Promise<GroundingData | null>;
  searchEvidence(
    ruleId: string,
    extraTerms?: string,
    signal?: AbortSignal,
  ): Promise<AnyRecord>;
  getCachedRepair?(candidateId?: string, failureId?: number): Promise<AnyRecord | null>;
}

const defaultBase = (
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")
).replace(/\/$/, "");

let currentApiBase = defaultBase;

export function getActiveApiBase(): string {
  return currentApiBase;
}

export function setActiveApiBase(url: string) {
  currentApiBase = (url || "").replace(/\/$/, "");
}

const LOCAL_STORAGE_KEY = "paysift_local_backend";

export function getStoredLocalBackend(): string | null {
  try {
    return localStorage.getItem(LOCAL_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredLocalBackend(url: string | null) {
  try {
    if (url) {
      localStorage.setItem(LOCAL_STORAGE_KEY, url);
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    }
  } catch {}
}

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = "ApiError";
  }
}

async function json<T>(
  url: string,
  init?: RequestInit,
  timeout = 15000,
): Promise<T> {
  const c = new AbortController();
  const timer = setTimeout(() => c.abort(), timeout);
  try {
    const r = await fetch(url, {
      ...init,
      signal: init?.signal
        ? AbortSignal.any([c.signal, init.signal])
        : c.signal,
    });
    if (!r.ok) {
      let body: any = null;
      try {
        body = await r.json();
      } catch {}
      let msg = body?.message || body?.detail || `Request failed (${r.status})`;
      if (r.status === 403 && body?.error === "disabled_in_hosted_mode") {
        msg = body.message || "Needs Docker and your own model key. Clone the repo and run it locally.";
      } else if (r.status === 429) {
        msg = body?.message || "Rate limit reached. Please wait a moment before trying again.";
      } else if (r.status === 400) {
        msg = body?.message || body?.detail || "Validation error: invalid request parameters.";
      }
      throw new ApiError(r.status, msg, body);
    }
    return await r.json();
  } catch (err: any) {
    if (err.name === "AbortError") {
      throw new Error("Operation timed out. If Docker is downloading images, retry.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function staticJson<T>(file: string): Promise<T> {
  return json<T>(`/data/${file}`);
}

export const staticSource: DataSource = {
  health: () =>
    staticJson<AnyRecord>("status.json").catch(() => ({ status: "snapshot", sandbox: false })),
  listRuns: async () => staticJson<AnyRecord[]>("index.json").catch(() => []),
  getRun: async (id) => {
    const ix = await staticJson<AnyRecord[]>("index.json").catch(() => []);
    const x = ix.find((a) => a.id === id || a.run_id === id);
    if (x) return staticJson<AnyRecord>(x.file);
    const example = await staticJson<AnyRecord>("real_example.json").catch(
      () => null,
    );
    if (example?.run_id === id) return example;
    throw new Error("Run is not present in the bundled snapshot.");
  },
  getKillMatrix: () => staticJson<AnyRecord>("kill_matrix.json"),
  breakIt: async () => {
    throw new Error(
      "Live scenario execution requires a local backend with Docker.",
    );
  },
  repair: async () => {
    throw new Error("Live repair requires a local backend with Docker and model keys.");
  },
  getCachedRepair: async (candidateId?: string, failureId?: number) => {
    try {
      const cand = candidateId || "3";
      const fail = failureId ?? 0;
      if (cand === "3" || cand.includes("strong_a/A/3")) {
        return await staticJson<AnyRecord>("repair/cache/3__0.json");
      }
      return null;
    } catch {
      return null;
    }
  },
  getScenarioVerdicts: () => staticJson<AnyRecord>("scenario_verdicts.json"),
  getSpec: () => fetch("/data/SPEC.md").then((r) => r.text()),
  getSpecHash: () =>
    fetch("/data/SPEC_HASH")
      .then((r) => r.text())
      .then((s) => s.trim()),
  getStatus: () => staticJson<AnyRecord>("status.json"),
  getPilotReport: () => fetch("/data/PILOT_REPORT.md").then((r) => r.text()),
  getEvidence: async () => {
    try {
      const raw = await staticJson<AnyRecord>("grounding.json").catch(() =>
        staticJson<AnyRecord>("runs/grounding.json"),
      );
      return normalizeGrounding(raw);
    } catch {
      return null;
    }
  },
  searchEvidence: async () => {
    throw new Error(
      "Live evidence search is available only in LIVE API mode.",
    );
  },
};

export const liveSource: DataSource = {
  health: (signal) => json(`${currentApiBase}/health`, { signal }, 6000),
  listRuns: (signal) => json(`${currentApiBase}/runs`, { signal }),
  getRun: (id, signal) => json(`${currentApiBase}/runs/${encodeURIComponent(id)}`, { signal }),
  getKillMatrix: (signal) => json(`${currentApiBase}/kill-matrix`, { signal }),
  breakIt: (candidate_id, scenario, signal) =>
    json(
      `${currentApiBase}/break`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id, scenario }),
        signal,
      },
      90000,
    ),
  repair: (candidate_id, failure_id, signal) =>
    json(
      `${currentApiBase}/repair`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id, failure_id }),
        signal,
      },
      90000,
    ),
  getCachedRepair: staticSource.getCachedRepair,
  getScenarioVerdicts: staticSource.getScenarioVerdicts,
  getSpec: staticSource.getSpec,
  getSpecHash: staticSource.getSpecHash,
  getStatus: staticSource.getStatus,
  getPilotReport: staticSource.getPilotReport,
  getEvidence: async (signal) => {
    try {
      const raw = await json<AnyRecord>(`${currentApiBase}/evidence`, { signal });
      return normalizeGrounding(raw);
    } catch {
      return staticSource.getEvidence(signal);
    }
  },
  searchEvidence: (ruleId, extraTerms, signal) =>
    json(
      `${currentApiBase}/evidence/search`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: ruleId,
          extra_terms: extraTerms || null,
        }),
        signal,
      },
      15000,
    ),
};

export type HealthProbeResult =
  | { ok: true; data: AnyRecord; sandbox: boolean }
  | { ok: false; error: string; blocked?: boolean; data?: AnyRecord };

export async function probeHealth(url: string, timeoutMs = 4000): Promise<HealthProbeResult> {
  const cleanUrl = url.replace(/\/$/, "");
  const c = new AbortController();
  const timer = setTimeout(() => c.abort(), timeoutMs);
  try {
    const r = await fetch(`${cleanUrl}/health`, {
      signal: c.signal,
      headers: { Accept: "application/json" },
    });
    if (!r.ok) {
      return { ok: false, error: `Backend responded with HTTP ${r.status}` };
    }
    const data = await r.json();
    return {
      ok: true,
      data,
      sandbox: Boolean(data?.sandbox),
    };
  } catch (e: any) {
    if (e.name === "AbortError") {
      return { ok: false, error: `Connection timed out after ${timeoutMs / 1000}s` };
    }
    const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
    const isHttpTarget = cleanUrl.startsWith("http://");
    if (isHttps && isHttpTarget) {
      return {
        ok: false,
        blocked: true,
        error: "Browser blocked the connection (HTTPS to HTTP localhost mixed content). Run the UI locally via 'npm run dev' to connect.",
      };
    }
    return {
      ok: false,
      error: `Local backend not reachable at ${cleanUrl}. Run 'python cli.py serve' first.`,
    };
  } finally {
    clearTimeout(timer);
  }
}

export type Mode = "local" | "hosted" | "static" | "down";

export interface SourceContext {
  source: DataSource;
  mode: Mode;
  sandbox: boolean;
  apiBase: string;
}

export async function chooseSource(): Promise<SourceContext> {
  const requested = import.meta.env.VITE_DATA_MODE || "auto";
  if (requested === "static") {
    return { source: staticSource, mode: "static", sandbox: false, apiBase: "" };
  }

  // 1. Check if user configured a local backend previously
  const storedLocal = getStoredLocalBackend();
  if (storedLocal) {
    const probe = await probeHealth(storedLocal, 4000);
    if (probe.ok && probe.sandbox) {
      setActiveApiBase(storedLocal);
      return {
        source: liveSource,
        mode: "local",
        sandbox: true,
        apiBase: storedLocal,
      };
    }
  }

  // 2. Check default API base if available
  if (defaultBase) {
    const probe = await probeHealth(defaultBase, 6000);
    if (probe.ok) {
      setActiveApiBase(defaultBase);
      if (probe.sandbox) {
        return {
          source: liveSource,
          mode: "local",
          sandbox: true,
          apiBase: defaultBase,
        };
      }
      return {
        source: liveSource,
        mode: "hosted",
        sandbox: false,
        apiBase: defaultBase,
      };
    }
  }

  // 3. Fallback to static snapshot with "down" mode
  return {
    source: staticSource,
    mode: "down",
    sandbox: false,
    apiBase: defaultBase,
  };
}

export const apiBase = defaultBase;
