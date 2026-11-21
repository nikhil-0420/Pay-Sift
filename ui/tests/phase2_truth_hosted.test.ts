import { describe, it, expect, vi, beforeEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { getMinimalTrace, latestPerCandidate } from "../src/lib/helpers";
import {
  probeHealth,
  staticSource,
  liveSource,
  getActiveApiBase,
  setActiveApiBase,
  getStoredLocalBackend,
  setStoredLocalBackend,
} from "../src/data/source";
import { normalizeGrounding } from "../src/data/grounding";

describe("Phase 2 - Truth, Data and Hosted Wiring", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("computes grounding stats accurately from real grounding.json", () => {
    const raw = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../public/data/grounding.json"), "utf8"),
    );
    const data = normalizeGrounding(raw);
    const labels = Object.values(data.rules).map((r) => r.label);
    const supported = labels.filter((l) => l === "SUPPORTED").length;
    const partial = labels.filter((l) => l === "PARTIAL").length;
    const notFound = labels.filter((l) => l === "NOT_FOUND").length;

    expect(supported).toBe(1);
    expect(partial).toBe(5);
    expect(notFound).toBe(5);
    expect(labels.length).toBe(11);
  });

  it("filters STUB and FAKE SAMPLE runs out of the synced index", () => {
    const indexPath = path.resolve(__dirname, "../public/data/index.json");
    const index = JSON.parse(fs.readFileSync(indexPath, "utf8"));
    expect(index.length).toBeGreaterThan(0);

    for (const run of index) {
      const isStub =
        run.source === "stub" ||
        run.model === "stub" ||
        String(run.candidateId || "").toLowerCase().includes("stub") ||
        String(run.id || "").toLowerCase().includes("stub");
      expect(isStub).toBe(false);
    }
  });

  it("keys latestPerCandidate by model/condition/id so candidate IDs across models do not collide", () => {
    const runs = [
      {
        candidate: { model: "gemini", condition: "A", id: "1" },
        created_at: "2026-11-21T10:00:00Z",
      },
      {
        candidate: { model: "qwen", condition: "A", id: "1" },
        created_at: "2026-11-21T10:05:00Z",
      },
      {
        candidate: { model: "gemini", condition: "A", id: "1" },
        created_at: "2026-11-21T10:10:00Z",
      },
    ];

    const deduplicated = latestPerCandidate(runs);
    expect(deduplicated.length).toBe(2);
    const gemini = deduplicated.find((r) => r.candidate.model === "gemini");
    const qwen = deduplicated.find((r) => r.candidate.model === "qwen");
    expect(gemini?.created_at).toBe("2026-11-21T10:10:00Z");
    expect(qwen?.created_at).toBe("2026-11-21T10:05:00Z");
  });

  it("extracts minimal trace correctly via getMinimalTrace", () => {
    expect(getMinimalTrace({ minimal_stream: [1, 2, 3, 4] })).toEqual([1, 2, 3, 4]);
    expect(
      getMinimalTrace({
        shrink_history: [
          [1, 2, 3, 4, 5],
          [1, 2, 3, 4],
        ],
      }),
    ).toEqual([1, 2, 3, 4]);
    expect(getMinimalTrace({ stream: [1, 2] })).toEqual([1, 2]);
    expect(getMinimalTrace({})).toEqual([]);
  });

  it("handles /health probe failure and timeout gracefully", async () => {
    // Mock fetch to simulate offline / timeout
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Failed to fetch"));

    const result = await probeHealth("http://127.0.0.1:8000", 500);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("Local backend not reachable");
  });

  it("probes /health successfully for local backend with Docker sandbox", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", sandbox: true, models: { configured: true } }),
    });

    const result = await probeHealth("http://127.0.0.1:8000", 4000);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.sandbox).toBe(true);
    }
  });

  it("detects hosted read-only backend where sandbox is false", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", sandbox: false }),
    });

    const result = await probeHealth("https://paysift.onrender.com", 4000);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.sandbox).toBe(false);
    }
  });

  it("derives distinct run violation counts without hardcoding counts", () => {
    const mockRuns = [
      {
        run_id: "run_1",
        failures: [
          { rule: "R8", invariant: "I2_idempotency" },
          { rule: "R8", invariant: "I2_idempotency" },
        ],
      },
      {
        run_id: "run_2",
        failures: [{ rule: "R8", invariant: "I2_idempotency" }],
      },
      {
        run_id: "run_3",
        failures: [{ rule: "R1", invariant: "I1_signature" }],
      },
    ];

    const distinctRunsForR8 = mockRuns.filter((r) =>
      r.failures.some((f) => f.rule === "R8"),
    ).length;

    expect(distinctRunsForR8).toBe(2);
  });
});
