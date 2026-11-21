import { afterEach, describe, expect, it, vi } from "vitest";
import fs from "node:fs";
import path from "node:path";
import {
  normalizeGrounding,
  readGrounding,
  citedRuleCount,
  joinEvidenceToFailures,
} from "../src/data/grounding";
import { staticSource } from "../src/data/source";

afterEach(() => vi.restoreAllMocks());

describe("grounding adapter", () => {
  it("returns null when the grounding file is missing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(readGrounding()).resolves.toBeNull();
  });

  it("maps the real backend shape including quote, reason, judge and sources", () => {
    const data = normalizeGrounding({
      generated_at: "2026-11-21T00:00:00Z",
      spec_sha: "sha",
      provider: "you.com",
      rules: {
        R3: {
          label: "SUPPORTED",
          convention: false,
          human_reviewed: true,
          quote: "verbatim quote",
          reason: "clear match",
          judge: { model: "judge-1", temperature: 0 },
          sources: [
            {
              id: "s1",
              url: "https://docs.example/r3",
              title: "Docs",
              snippet: "A short excerpt",
              rank: 1,
              query: "r3",
              retrieved_at: "2026-11-20T00:00:00Z",
            },
          ],
        },
      },
    });
    expect(data?.provider).toBe("you.com");
    expect(data?.rules.R3.quote).toBe("verbatim quote");
    expect(data?.rules.R3.reason).toBe("clear match");
    expect(data?.rules.R3.sources[0].domain).toBe("docs.example");
    expect(citedRuleCount(data)).toBe(1);
  });

  it("uses NOT_JUDGED for an unknown label and rejects unsafe source URLs", () => {
    const data = normalizeGrounding({
      rules: {
        R1: {
          label: "MAYBE",
          sources: [{ id: "bad", url: "javascript:alert(1)", title: "bad" }],
        },
      },
    });
    expect(data?.rules.R1.label).toBe("NOT_JUDGED");
    expect(data?.rules.R1.sources).toHaveLength(0);
  });

  it("parses the real grounding.json with 11 rules and handles human overrides", () => {
    const filePath = path.resolve("public/data/grounding.json");
    expect(fs.existsSync(filePath)).toBe(true);
    const raw = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    const data = normalizeGrounding(raw);
    expect(data).not.toBeNull();
    expect(data?.provider).toBe("you.com");
    expect(Object.keys(data?.rules || {})).toHaveLength(11);
    // Check human overrides applied in K4
    expect(data?.rules.R8.human_reviewed).toBe(true);
    expect(data?.rules.R8.label).toBe("PARTIAL");
    expect(data?.rules.R9.human_reviewed).toBe(true);
    expect(data?.rules.R9.label).toBe("PARTIAL");
    expect(data?.rules.R10.human_reviewed).toBe(true);
    expect(data?.rules.R10.label).toBe("PARTIAL");
    // Check convention rules
    expect(data?.rules.R0.convention).toBe(true);
    expect(data?.rules.R0.label).toBe("NOT_FOUND");
    // Check supported rule
    expect(data?.rules.R1.label).toBe("SUPPORTED");
  });

  it("handles fixtures with missing sources, undefined fields, and empty objects gracefully", () => {
    const data = normalizeGrounding({
      rules: {
        R0: {
          label: "NOT_FOUND",
          convention: true,
          // sources missing
        },
        R2: {
          label: "NOT_FOUND",
          convention: true,
          sources: [],
        },
        R4: {
          label: "NOT_FOUND",
          convention: true,
          sources: null,
        },
        R5: {
          // empty rule
        },
      },
    });
    expect(data?.rules.R0.sources).toEqual([]);
    expect(data?.rules.R2.sources).toEqual([]);
    expect(data?.rules.R4.sources).toEqual([]);
    expect(data?.rules.R5.label).toBe("NOT_JUDGED");
    expect(data?.rules.R5.sources).toEqual([]);
  });

  it("joins evidence to failures by rule id", () => {
    const data = normalizeGrounding({
      rules: {
        R1: {
          label: "SUPPORTED",
          convention: false,
          human_reviewed: false,
          sources: [],
          quote: "",
          reason: "Signature verification verified",
        },
      },
    });
    const failures = [
      { id: "f1", rule: "R1", invariant: "I1_signature" },
      { id: "f2", rule: "R99", invariant: "I99" },
      { id: "f3" },
    ];
    const joined = joinEvidenceToFailures(failures, data);
    expect(joined[0].evidence?.label).toBe("SUPPORTED");
    expect(joined[0].evidence?.reason).toBe("Signature verification verified");
    expect(joined[1].evidence).toBeUndefined();
    expect(joined[2].evidence).toBeUndefined();
  });

  it("implements staticSource.getEvidence and searchEvidence guard", async () => {
    const raw = fs.readFileSync(path.resolve("public/data/grounding.json"), "utf-8");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("grounding.json")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(raw)) });
        }
        return Promise.resolve({ ok: false });
      }),
    );
    const ev = await staticSource.getEvidence();
    expect(ev).not.toBeNull();
    expect(Object.keys(ev?.rules || {})).toHaveLength(11);
    await expect(staticSource.searchEvidence("R1")).rejects.toThrow(
      "Live evidence search is available only in LIVE API mode.",
    );
  });

  it("does not include the development fixture marker in the production bundle", async () => {
    const fsPromises = await import("node:fs/promises");
    if (!(await fsPromises.stat("dist/assets").catch(() => null))) return;
    const files = await fsPromises.readdir("dist/assets");
    const javascript = (
      await Promise.all(
        files
          .filter((file) => file.endsWith(".js"))
          .map((file) => fsPromises.readFile(`dist/assets/${file}`, "utf8")),
      )
    ).join("\n");
    expect(javascript).not.toContain("sample-spec-sha");
  });
});
