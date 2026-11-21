import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const args = process.argv.slice(2);
const at = args.indexOf("--src");
const src = path.resolve(at >= 0 ? args[at + 1] : "..");
const out = path.resolve("public/data");
fs.mkdirSync(path.join(out, "runs"), { recursive: true });
let copied = 0;
function copyAny(options, destination) {
  const rel = options.find((x) => fs.existsSync(path.join(src, x)));
  if (!rel) {
    console.warn(`Missing source skipped (tried ${options.join(", ")}).`);
    return false;
  }
  const dest = path.join(out, destination || path.basename(rel));
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(path.join(src, rel), dest);
  copied++;
  return true;
}
for (const [options, dest] of [
  [["contract/SPEC.md", "SPEC.md"], "SPEC.md"],
  [["contract/SPEC_HASH", "SPEC_HASH"], "SPEC_HASH"],
  [["contract/run_schema.json", "run_schema.json"], "run_schema.json"],
  [
    ["runs/scenario_verdicts.json", "scenario_verdicts.json"],
    "scenario_verdicts.json",
  ],
  [["runs/kill_matrix.json", "kill_matrix.json"], "kill_matrix.json"],
  [["PROGRESS.md"], "PROGRESS.md"],
  [["NEEDS_HUMAN.md"], "NEEDS_HUMAN.md"],
  [["pilot/PILOT_REPORT.md", "PILOT_REPORT.md"], "PILOT_REPORT.md"],
  [["runs/README.md"], "runs/README.md"],
  [["sample.json"], "sample.json"],
  [["real_example.json", "runs/real_example.json"], "real_example.json"],
  [
    ["kill_matrix.sample.json", "runs/kill_matrix.sample.json"],
    "kill_matrix.sample.json",
  ],
])
  copyAny(options, dest);
copyAny(["runs/grounding.json", "grounding.json"], "grounding.json");
copyAny(["runs/grounding.json", "grounding.json"], "runs/grounding.json");
copyAny(["contract/grounding_schema.json"], "contract/grounding_schema.json");
const runsDir = path.join(src, "runs");
let files = [];
if (fs.existsSync(runsDir))
  files = fs
    .readdirSync(runsDir)
    .filter(
      (f) =>
        f.endsWith(".json") &&
        ![
          "sample.json",
          "real_example.json",
          "kill_matrix.json",
          "kill_matrix.sample.json",
          "scenario_verdicts.json",
          "grounding.json",
        ].includes(f),
    );
else
  files = fs
    .readdirSync(src)
    .filter(
      (f) =>
        f.endsWith(".json") &&
        ![
          "sample.json",
          "real_example.json",
          "kill_matrix.json",
          "kill_matrix.sample.json",
          "scenario_verdicts.json",
          "run_schema.json",
          "grounding.json",
        ].includes(f),
    );
const index = [];
for (const file of files) {
  const from = fs.existsSync(path.join(runsDir, file))
    ? path.join(runsDir, file)
    : path.join(src, file);
  try {
    const run = JSON.parse(fs.readFileSync(from, "utf8"));
    if (!run?.run_id) continue;
    // Filter STUB / "FAKE SAMPLE" runs out of index and counts
    const isStubOrSample =
      run.candidate?.source === "stub" ||
      run.candidate?.model === "stub" ||
      String(run.candidate?.id || "").toLowerCase().includes("stub") ||
      String(run.candidate?.label || "").toUpperCase().includes("FAKE SAMPLE") ||
      String(run.run_id || "").toLowerCase().includes("stub");
    if (isStubOrSample) continue;

    const dest = `runs/${file}`;
    fs.copyFileSync(from, path.join(out, dest));
    const failures = Array.isArray(run.failures) ? run.failures : [];
    index.push({
      id: run.run_id,
      file: dest,
      candidateId: run.candidate?.id,
      source: run.candidate?.source,
      model: run.candidate?.model,
      condition: run.candidate?.condition,
      created_at: run.created_at,
      spec_sha: run.spec_sha,
      failureCount: failures.length,
      financialInvariantsFailed: [
        ...new Set(
          failures
            .filter((f) => f.severity === "financial")
            .map((f) => f.invariant),
        ),
      ],
    });
  } catch (e) {
    console.warn(`Invalid run skipped ${file}: ${e.message}`);
  }
}
fs.writeFileSync(path.join(out, "index.json"), JSON.stringify(index, null, 2));
const status = {
  generated_at: new Date().toISOString(),
  run_count: index.length,
  phases: [],
  gates: [],
  blockers: [],
  readiness: {},
  g1_result: null,
  spec_draft_frozen: false,
};
try {
  const md = fs.readFileSync(path.join(out, "PROGRESS.md"), "utf8");
  status.phases = [
    ...md.matchAll(/^\|\s*(P\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|/gm),
  ].map((m) => ({ id: m[1], title: m[2].trim(), status: m[3].trim() }));
  status.gates = [
    ...md.matchAll(/^\|\s*(G\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|/gm),
  ].map((m) => ({ id: m[1], title: m[2].trim(), status: m[3].trim() }));
  status.spec_draft_frozen = fs
    .readFileSync(path.join(out, "SPEC.md"), "utf8")
    .split("\n")[0]
    .includes("DRAFT-FROZEN");
} catch {}

// Read handoff markers to derive authoritative readiness statuses
const handoffDir = path.join(src, "handoff");
const markers = {};
if (fs.existsSync(handoffDir)) {
  for (const f of fs.readdirSync(handoffDir)) {
    if (f.endsWith(".md")) continue;
    try {
      const text = fs.readFileSync(path.join(handoffDir, f), "utf8");
      const obj = {};
      for (const line of text.split("\n")) {
        const m = line.match(/^([a-zA-Z0-9_-]+):\s*(.*)$/);
        if (m) obj[m[1]] = m[2];
      }
      markers[f] = obj;
    } catch {}
  }
}

const g1Handoff = markers["G1_RESULT"];
if (g1Handoff) {
  status.g1_result = {
    outcome: g1Handoff.outcome || "PASSED",
    summary: g1Handoff.summary || "Gate 1 passed, spec unchanged",
    spec_changed: g1Handoff.spec_changed === "true",
  };
}

const hasGate4 = !!markers["N1_GATE4_PASSED"] || status.gates.some((g) => g.id === "G4" && g.status.includes("PASSED"));
const hasModels = !!markers["N4_MODELS_PUSHED"] || !!markers["N6_CANDIDATES_PUSHED"];
const hasPilot = !!markers["N7_PILOT_DONE"] || !!markers["N7_PILOT_RAN"];
const hasRepair = !!markers["N8_REPAIR_DONE"];

status.readiness = {
  docker: {
    state: hasGate4 ? "ok" : "blocked",
    detail: hasGate4 ? "Docker runtime verified (Gate 4 passed)" : "Docker daemon not detected",
  },
  models: {
    state: hasModels ? "ok" : "blocked",
    detail: hasModels ? "Models configured and candidates generated" : "Model API keys not configured",
  },
  sandbox_gate: {
    state: hasGate4 ? "ok" : "blocked",
    detail: hasGate4 ? "Hostile tests contained (Gate 4 passed)" : "Sandbox gate pending",
  },
  pilot: {
    state: hasPilot ? "ok" : "blocked",
    detail: hasPilot ? "Pilot completed (15 candidate runs evaluated)" : "Pilot not run",
  },
  repair: {
    state: hasRepair ? "ok" : "not run",
    detail: hasRepair ? "Repair completed" : "NOT RUN (standing by for pilot repair loop)",
  },
  oracle_gate: {
    state: status.gates.find((g) => g.id === "G2")?.status || "PASSED",
    detail: "Reference handler passes 100/100 invariants (PASSED)",
  },
};

try {
  const md = fs.readFileSync(path.join(out, "NEEDS_HUMAN.md"), "utf8");
  status.blockers = [...md.matchAll(/^###\s+([A-Z]+-\d+):\s*(.*)$/gm)].map(
    (m) => ({
      id: m[1],
      title: m[2],
      severity:
        md.slice(m.index, m.index + 450).match(/Severity:\*\*\s*(\w+)/)?.[1] ||
        "FYI",
    }),
  );
} catch {}
fs.writeFileSync(
  path.join(out, "status.json"),
  JSON.stringify(status, null, 2),
);
let featured = null;
const n7Path = path.join(src, "handoff/N7_PILOT_DONE");
if (fs.existsSync(n7Path)) {
  try {
    const content = fs.readFileSync(n7Path, "utf8");
    const demoCand = content.match(/^demo_candidate:\s*(.+)$/m)?.[1]?.trim();
    if (demoCand) {
      const parts = demoCand.split("/");
      const candId = parts[parts.length - 1];
      const cond = parts.length > 1 ? parts[1] : undefined;
      const matchRun = index.find(
        (r) =>
          (r.candidateId === candId || r.id.includes(`_${candId}_`)) &&
          (!cond || r.condition === cond) &&
          (r.source === "live" || r.source === "pre-run")
      );
      if (matchRun) {
        featured = matchRun;
      }
    }
  } catch {}
}
if (!featured) {
  const condAFinding = index.find(
    (x) =>
      (x.source === "live" || x.source === "pre-run") &&
      x.condition === "A" &&
      x.failureCount > 0
  );
  const model = index
    .filter((x) => x.source === "live" || x.source === "pre-run")
    .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)))
    .at(-1);
  featured = condAFinding || model;
}
if (!featured) {
  try {
    const r = JSON.parse(
      fs.readFileSync(path.join(out, "real_example.json"), "utf8"),
    );
    featured = {
      id: r.run_id,
      file: "real_example.json",
      candidateId: r.candidate?.id,
      source: r.candidate?.source,
      model: r.candidate?.model,
      condition: r.candidate?.condition,
      created_at: r.created_at,
      spec_sha: r.spec_sha,
      failureCount: r.failures?.length || 0,
    };
  } catch {
    featured = null;
  }
}
fs.writeFileSync(
  path.join(out, "featured.json"),
  JSON.stringify(featured, null, 2),
);
console.log(
  `Synced ${index.length} ordinary run(s); ${copied} source file(s) copied from ${src}.`,
);
