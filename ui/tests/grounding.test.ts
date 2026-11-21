import { afterEach, describe, expect, it, vi } from "vitest";
import {
  normalizeGrounding,
  readGrounding,
  citedRuleCount,
} from "../src/data/grounding";

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

  it("does not include the development fixture marker in the production bundle", async () => {
    const fs = await import("node:fs/promises");
    if (!(await fs.stat("dist/assets").catch(() => null))) return;
    const files = await fs.readdir("dist/assets");
    const javascript = (
      await Promise.all(
        files
          .filter((file) => file.endsWith(".js"))
          .map((file) => fs.readFile(`dist/assets/${file}`, "utf8")),
      )
    ).join("\n");
    expect(javascript).not.toContain("sample-spec-sha");
  });
});
