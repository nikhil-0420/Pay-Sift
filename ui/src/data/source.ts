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
}
const base = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
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
      let msg = `Request failed (${r.status})`;
      try {
        const e = await r.json();
        msg = e.detail || e.message || msg;
      } catch {}
      throw new Error(msg);
    }
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}
async function staticJson<T>(file: string): Promise<T> {
  return json<T>(`/data/${file}`);
}
export const staticSource: DataSource = {
  health: () =>
    staticJson<AnyRecord>("status.json").catch(() => ({ status: "snapshot" })),
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
      "Live scenario execution is available only in LIVE API mode.",
    );
  },
  repair: async () => {
    throw new Error("Live repair is available only in LIVE API mode.");
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
  health: () => json(`${base}/health`),
  listRuns: () => json(`${base}/runs`),
  getRun: (id) => json(`${base}/runs/${encodeURIComponent(id)}`),
  getKillMatrix: () => json(`${base}/kill-matrix`),
  breakIt: (candidate_id, scenario, signal) =>
    json(`${base}/break`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id, scenario }),
      signal,
    }),
  repair: (candidate_id, failure_id, signal) =>
    json(
      `${base}/repair`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id, failure_id }),
        signal,
      },
      180000,
    ),
  getScenarioVerdicts: staticSource.getScenarioVerdicts,
  getSpec: staticSource.getSpec,
  getSpecHash: staticSource.getSpecHash,
  getStatus: staticSource.getStatus,
  getPilotReport: staticSource.getPilotReport,
  getEvidence: async (signal) => {
    try {
      const raw = await json<AnyRecord>(`${base}/evidence`, { signal });
      return normalizeGrounding(raw);
    } catch {
      return staticSource.getEvidence(signal);
    }
  },
  searchEvidence: (ruleId, extraTerms, signal) =>
    json(
      `${base}/evidence/search`,
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
export type Mode = "live" | "static" | "down";
export async function chooseSource(): Promise<{
  source: DataSource;
  mode: Mode;
}> {
  const requested = import.meta.env.VITE_DATA_MODE || "auto";
  if (requested === "static") return { source: staticSource, mode: "static" };
  if (requested === "live") return { source: liveSource, mode: "live" };
  try {
    await Promise.race([
      liveSource.health(),
      new Promise((_, rej) =>
        setTimeout(() => rej(new Error("timeout")), 1500),
      ),
    ]);
    return { source: liveSource, mode: "live" };
  } catch {
    return { source: staticSource, mode: "down" };
  }
}
export const apiBase = base;
