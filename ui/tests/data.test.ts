import { it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { normalizeRun, invariantKeys } from "../src/lib/helpers";
it("normalizes every supplied bundled run without dropping failures", () => {
  const dir = "public/data/runs";
  const files = fs
    .readdirSync(dir)
    .filter((x) => x.endsWith(".json") && x !== "grounding.json")
    .map((f) => path.join(dir, f))
    .concat(["public/data/real_example.json", "public/data/sample.json"]);
  for (const file of files) {
    const raw = JSON.parse(fs.readFileSync(file, "utf8"));
    const f = path.basename(file);
    const n = normalizeRun(raw);
    expect(n.run_id).toBe(raw.run_id);
    expect(n.failures.length).toBe(raw.failures?.length || 0);
    expect(invariantKeys(n.results).length).toBeGreaterThan(0);
  }
});
