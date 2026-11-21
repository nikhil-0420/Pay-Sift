import React, { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Command } from "cmdk";
import DOMPurify from "dompurify";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  Check,
  ChevronDown,
  CircleHelp,
  Copy,
  Database,
  ExternalLink,
  FileJson,
  Filter,
  FlaskConical,
  Keyboard,
  Menu,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  Terminal,
  TriangleAlert,
  X,
} from "lucide-react";
import "./styles.css";
import {
  apiBase,
  chooseSource,
  staticSource,
  liveSource,
  type DataSource,
  type Mode,
} from "./data/source";
import {
  readGrounding,
  citedRuleCount,
  type GroundingData,
  WHY_BUG_ENDPOINT,
} from "./data/grounding";
import {
  CopyChip,
  DesignedEmpty,
  EvidencePanel,
  EvidenceLanding,
  EventTimeline,
  KillMatrixHeatmap,
  LedgerReceipt,
  PipelineDiagram,
  RuleBadge,
  ShrinkPlayer,
  StatusBoard,
  DiffViewer,
  SkeletonBlock,
  EvidenceGaps,
  EvidenceChip,
  SourceCard,
} from "./components";
import {
  alignSubsequence,
  eventSummary,
  formatMoney,
  invariantKeys,
  isFinancial,
  latestPerCandidate,
  moneyDelta,
  normalizeRun,
  sourceLabel,
} from "./lib/helpers";
type Ctx = { source: DataSource; mode: Mode; setRaw: (x: any) => void };
const C = React.createContext<Ctx>({
  source: staticSource,
  mode: "static",
  setRaw: () => {},
});
const qc = new QueryClient();
const useApp = () => React.useContext(C);
const useData = () => {
  const { source } = useApp();
  return useQuery({
    queryKey: ["runs", source === liveSource ? "live" : "static"],
    queryFn: async () => {
      const index = await source.listRuns();
      return Promise.all(
        index.map(async (x) => {
          if (x.results && x.failures) return normalizeRun(x);
          const id = x.run_id || x.id;
          try {
            return normalizeRun(await source.getRun(id));
          } catch {
            return normalizeRun(x);
          }
        }),
      );
    },
  });
};
function query<T = any>(key: string, fn: () => Promise<T>) {
  const { source } = useApp();
  return useQuery<T>({
    queryKey: [key, source === liveSource ? "live" : "static"],
    queryFn: fn,
  });
}
const useGrounding = () => {
  const { source } = useApp();
  return useQuery<GroundingData | null>({
    queryKey: ["grounding", source === liveSource ? "live" : "static"],
    queryFn: () => source.getEvidence(),
  });
};
function Badge({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function ClassBadge({ value }: any) {
  const label =
    typeof value === "string" ? value : value?.label || "unreviewed";
  const by = typeof value === "object" && value ? value.by : null;
  const note = typeof value === "object" && value ? value.note : null;
  return (
    <span title={note || ""}>
      <Badge
        tone={
          by === "agent-proposed"
            ? "amber"
            : by === "human-reviewed"
              ? "green"
              : "muted"
        }
      >
        {label}
        {by ? ` · ${by}` : ""}
      </Badge>
      {note && <span className="source-line"> {note}</span>}
    </span>
  );
}
function Source({ candidate }: any) {
  const src = candidate?.source,
    id = String(candidate?.id || "");
  const label =
    src === "extra-mutant" || id.startsWith("x")
      ? "EXTRA-MUTANT"
      : src === "mutant" || id.startsWith("m")
        ? "HAND-WRITTEN MUTANT"
        : src === "reference" || id === "reference"
          ? "REFERENCE"
          : src === "model" || ["live", "pre-run"].includes(src)
            ? "MODEL"
            : candidate?.condition === "B"
              ? "ILLUSTRATIVE"
              : sourceLabel(src);
  const tone =
    label === "HAND-WRITTEN MUTANT" || label === "EXTRA-MUTANT"
      ? "red"
      : label === "REFERENCE"
        ? "green"
        : label === "MODEL"
          ? "amber"
          : "muted";
  return (
    <div className="row">
      <Badge tone={tone}>{label}</Badge>
      <span>{candidate?.label || candidate?.id || "source not supplied"}</span>
    </div>
  );
}
function RawButton({ data }: { data: any }) {
  const { setRaw } = useApp();
  return (
    <button className="btn" onClick={() => setRaw(data)}>
      <FileJson size={14} /> View raw JSON
    </button>
  );
}
function Hash({ value }: { value: string }) {
  return <CopyChip value={value || ""} label={value?.slice(0, 12) || "—"} />;
}
function DataStatus() {
  const { mode } = useApp();
  return (
    <span
      className={`statusbar ${mode === "live" ? "is-live" : "is-static"}`}
      title={
        mode === "live"
          ? "Connected to the configured API"
          : "Using the bundled static snapshot; live actions are unavailable"
      }
    >
      <i aria-hidden="true" />
      {mode === "live" ? "LIVE API" : "STATIC SNAPSHOT"}
    </span>
  );
}
let specText = "";
let specHash = "";
function DraftBanner() {
  const { source } = useApp();
  const { data: spec } = query("spec", () => source.getSpec());
  specText = spec || "";
  return spec?.split("\n")[0].includes("DRAFT-FROZEN") ? (
    <div className="specbanner">
      Specification DRAFT-FROZEN · human review pending
    </div>
  ) : null;
}
function Shell() {
  const [raw, setRaw] = useState<any>(null),
    [ctx, setCtx] = useState<{ source: DataSource; mode: Mode }>({
      source: staticSource,
      mode: "static",
    }),
    [palette, setPalette] = useState(false),
    [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    let active = true;
    const sync = async () => {
      const x = await chooseSource();
      if (active) setCtx(x);
    };
    sync();
    const id = setInterval(async () => {
      if (
        import.meta.env.VITE_DATA_MODE &&
        import.meta.env.VITE_DATA_MODE !== "auto"
      )
        return;
      try {
        await liveSource.health();
        if (active) setCtx({ source: liveSource, mode: "live" });
      } catch {
        if (active) setCtx({ source: staticSource, mode: "down" });
      }
    }, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
      if (e.key === "Escape") {
        setPalette(false);
        setRaw(null);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);
  const location = useLocation();
  useEffect(() => {
    setPalette(false);
    setMobileOpen(false);
  }, [location.pathname]);
  const value = useMemo(() => ({ ...ctx, setRaw }), [ctx]);
  const nav = [
    ["/runs", "Findings"],
    ["/kill-matrix", "Kill matrix"],
    ["/break", "Break it"],
    ["/repair", "Repair"],
    ["/pilot", "Pilot"],
    ["/spec", "Spec"],
    ["/method", "Method"],
  ];
  return (
    <C.Provider value={value}>
      <div className="app">
        {import.meta.env.DEV &&
          new URLSearchParams(location.search).get("fixture") ===
            "evidence" && (
            <div className="sample-ribbon">
              SAMPLE DATA · development-only evidence fixture
            </div>
          )}
        <header className="nav">
          <Link to="/" className="brand" aria-label="PaySift home">
            <i className="brandmark" />
            PaySift
          </Link>
          <nav className="navlinks" aria-label="Primary navigation">
            {nav.map(([to, t]) => (
              <NavLink key={to} to={to}>
                {({ isActive }) => (
                  <span className="nav-link-inner">
                    {t}
                    {isActive && (
                      <motion.i
                        className="nav-indicator"
                        layoutId="active-nav"
                        transition={{
                          type: "spring",
                          stiffness: 420,
                          damping: 34,
                        }}
                      />
                    )}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
          <DataStatus />
          <button
            className="keyhint command-trigger"
            onClick={() => setPalette(true)}
            aria-label="Open command palette"
          >
            <span>⌘K</span>
          </button>
          <button
            className="mobile-menu btn"
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav-sheet"
            onClick={() => setMobileOpen((v) => !v)}
          >
            <Menu size={17} />
            <span>Menu</span>
          </button>
        </header>
        {mobileOpen && (
          <div id="mobile-nav-sheet" className="mobile-sheet">
            <div className="mobile-sheet-head">
              <b>PaySift navigation</b>
              <button
                className="btn"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
              >
                <X size={16} />
              </button>
            </div>
            {nav.map(([to, t]) => (
              <NavLink key={to} to={to}>
                {t}
                <ArrowRight size={14} />
              </NavLink>
            ))}
            <button className="btn" onClick={() => setPalette(true)}>
              <Search size={15} /> Search pages, rules and runs
            </button>
          </div>
        )}
        {ctx.source === staticSource && <DraftBanner />}
        <Suspense
          fallback={
            <div className="page">
              <div className="skeleton" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/runs" element={<Runs />} />
            <Route path="/runs/:runId" element={<RunDetail />} />
            <Route path="/runs/:runId/failures/:index" element={<Failure />} />
            <Route path="/kill-matrix" element={<KillMatrix />} />
            <Route path="/break" element={<BreakPage />} />
            <Route path="/repair" element={<Repair />} />
            <Route path="/pilot" element={<Pilot />} />
            <Route path="/spec" element={<Spec />} />
            <Route path="/method" element={<Method />} />
            <Route path="/gaps" element={<Gaps />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/status" element={<Status />} />
            <Route path="/dev/contract" element={<DevContract />} />
            <Route path="/dev/sample" element={<Samples />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
        <footer className="footer">
          <span>
            <Link className="footer-brand" to="/">
              PaySift
            </Link>{" "}
            / FORENSIC LEDGER
          </span>
          <span>
            <Link to="/method">Method</Link> · <Link to="/status">Status</Link>{" "}
            · Spec {specHash.slice(0, 10)}
          </span>
          <span>Built for BEYOND 9TO5</span>
        </footer>
        {raw && (
          <div className="raw" onClick={() => setRaw(null)}>
            <div
              className="rawbox"
              role="dialog"
              aria-modal="true"
              aria-label="Raw source JSON"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="row">
                <b>Raw source JSON</b>
                <span className="spacer" />
                <button aria-label="Close" onClick={() => setRaw(null)}>
                  <X />
                </button>
              </div>
              <pre>{JSON.stringify(raw, null, 2)}</pre>
            </div>
          </div>
        )}
        {palette && <Palette onClose={() => setPalette(false)} />}
      </div>
    </C.Provider>
  );
}
function parseRules(spec: string) {
  return spec.split("\n").flatMap((line) => {
    const match = line.match(
      /^\|\s*\*\*(R\d+)\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|\s*(.*?)\s*\|/,
    );
    return match ? [{ id: match[1], title: match[2], body: match[3] }] : [];
  });
}
function Palette({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const { data: runs = [] } = useData();
  const { source } = useApp();
  const { data: matrix } = query("palette-matrix", () =>
    source.getKillMatrix(),
  );
  const { data: spec } = query("palette-spec", () => source.getSpec());
  const rules = parseRules(spec || "");
  const go = (to: string) => {
    nav(to);
    onClose();
  };
  const pages = [
    ["Home", "/"],
    ["Findings", "/runs"],
    ["Kill matrix", "/kill-matrix"],
    ["Break it", "/break"],
    ["Repair", "/repair"],
    ["Pilot", "/pilot"],
    ["Specification", "/spec"],
    ["Method", "/method"],
    ["Evidence and spec gaps", "/gaps"],
    ["Status", "/status"],
    ["Guided demo", "/demo"],
  ];
  const candidates = [
    ...(matrix?.rows || []).map((row: any) => ({
      id: row.id,
      label: row.label,
    })),
    ...runs.map((run: any) => ({
      id: run.candidate?.id,
      label: run.candidate?.label,
      run_id: run.run_id,
    })),
  ];
  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <Command.Dialog
        open
        onOpenChange={(open) => !open && onClose()}
        label="PaySift command palette"
        className="command-palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="palette-input">
          <Search size={17} />
          <Command.Input
            placeholder="Search pages, rules, candidates and runs…"
            autoFocus
          />
          <kbd>ESC</kbd>
        </div>
        <Command.List>
          <Command.Empty>No matching pages or records.</Command.Empty>
          <Command.Group heading="Pages">
            {pages.map(([label, to]) => (
              <Command.Item
                key={to}
                value={`${label} ${to}`}
                onSelect={() => go(to)}
              >
                {label}
                <span>{to}</span>
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Rules">
            {rules.map((rule: any) => (
              <Command.Item
                key={rule.id}
                value={`${rule.id} ${rule.title}`}
                onSelect={() => go(`/spec#${rule.id.toLowerCase()}`)}
              >
                {rule.id} · {rule.title}
                <span>Open rule</span>
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Candidates and runs">
            {candidates.map((item: any, index: number) => (
              <Command.Item
                key={`${item.id}-${item.run_id || index}`}
                value={`${item.id} ${item.label || ""} ${item.run_id || ""}`}
                onSelect={() =>
                  go(
                    item.run_id
                      ? `/runs/${item.run_id}`
                      : `/runs?candidate=${encodeURIComponent(item.id)}`,
                  )
                }
              >
                {item.id} · {item.label || "candidate"}
                <span>{item.run_id || "candidate"}</span>
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command.Dialog>
    </div>
  );
}
function Title({
  eyebrow,
  title,
  sub,
}: {
  eyebrow: string;
  title: string;
  sub?: string;
}) {
  return (
    <div>
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      {sub && <p className="lead">{sub}</p>}
    </div>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <b>{title}</b>
      <div>{children}</div>
    </div>
  );
}
function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: any;
  action?: any;
}) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
function Home() {
  const { source } = useApp();
  const { data: runs = [] } = useData();
  const { data: km } = query("matrix", () => source.getKillMatrix());
  const { data: status } = query("status", () => source.getStatus());
  const { data: specSHA } = query("landing-sha", () => source.getSpecHash());
  const { data: example } = query("featured-example", () =>
    fetch("/data/real_example.json")
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  );
  const { data: grounding = null } = useGrounding();
  const modelRuns = runs.filter((r) =>
    ["live", "pre-run"].includes(r.candidate?.source),
  );
  const financial = modelRuns
    .flatMap((r) =>
      r.failures
        .filter((f: any) => isFinancial(f.invariant))
        .map((f: any) => ({ r, f })),
    )
    .sort(
      (a: any, b: any) =>
        (a.f.minimal_stream?.length || 0) - (b.f.minimal_stream?.length || 0),
    )[0];
  const fallback =
    !financial && example?.failures?.length
      ? {
          r: normalizeRun(example),
          f:
            example.failures.find((f: any) => isFinancial(f.invariant)) ||
            example.failures[0],
        }
      : null;
  const featured = financial || fallback;
  const rows = km?.rows || [];
  const hand = rows.filter((r: any) => r.source === "mutant"),
    extra = rows.filter((r: any) => r.source === "extra-mutant"),
    mutants = [...hand, ...extra];
  const killed = mutants.filter((r: any) => r.killed).length;
  const delta = featured?.f ? moneyDelta(featured.f) : null;
  const allFailures = runs.flatMap((r: any) => r.failures || []);
  const largest = allFailures.length
    ? Math.max(...allFailures.map((f: any) => f.minimal_stream?.length || 0))
    : null;
  const reproduction = allFailures
    .map((f: any) => f.repro)
    .filter(Boolean)
    .reduce(
      (a: any, x: any) => ({
        done: a.done + (Number(x.reproduced) || 0),
        total: a.total + (Number(x.runs) || 0),
      }),
      { done: 0, total: 0 },
    );
  const blockers = status?.blockers || [];
  const gate = (status?.gates || []).find((g: any) => g.id === "G4");
  const match = (rx: RegExp) =>
    blockers.find((b: any) => rx.test(`${b.title} ${b.id}`));
  const state = (b: any, ok: boolean): "ok" | "blocked" | "not run" =>
    b ? "blocked" : ok ? "ok" : "not run";
  const board = [
    {
      label: "Docker",
      state: state(match(/docker/i), false),
      detail: match(/docker/i)?.title || "No Docker status supplied",
    },
    {
      label: "Models",
      state: state(match(/model|api key/i), false),
      detail: match(/model|api key/i)?.title || "No model status supplied",
    },
    {
      label: "Sandbox gate",
      state: gate?.status?.includes("PASSED") ? "ok" : "blocked",
      detail: gate?.status || "No sandbox status supplied",
    },
    {
      label: "Pilot",
      state: state(match(/pilot/i), modelRuns.length > 0),
      detail:
        match(/pilot/i)?.title || `${modelRuns.length} sourced model runs`,
    },
    {
      label: "Repair",
      state: state(match(/repair/i), false),
      detail: match(/repair/i)?.title || "No repair result recorded",
    },
  ];
  return (
    <main className="page">
      <div className="hero">
        <div className="hero-copy">
          <div className="eyebrow">Payment handler verification / v1.0</div>
          <h1>
            AI writes payment code that passes demos.{" "}
            <em>PaySift finds the rupee it invents.</em>
          </h1>
          <p className="lead">
            PaySift stress-tests webhook handlers against a financial contract,
            then shrinks a failing event stream to the smallest recorded
            sequence that still breaks the ledger.
          </p>
          <div className="actions">
            <Link
              className="btn primary"
              to={
                featured
                  ? `/runs/${featured.r.run_id}/failures/${featured.r.failures.indexOf(featured.f)}`
                  : "/runs"
              }
            >
              <Play size={15} /> Watch the recorded failure
            </Link>
            <Link className="btn" to="/runs">
              Explore findings <ArrowRight size={15} />
            </Link>
          </div>
        </div>
        <div className="hero-proof">
          <div className="eyebrow">
            Recorded failure / source classification retained
          </div>
          {featured ? (
            <>
              <Source candidate={featured.r.candidate} />
              <div className="hero-receipts">
                <motion.div className="receipt-print">
                  <div className="receipt-label">Expected</div>
                  <b>
                    {featured.f.invariant} · Rule {featured.f.rule}
                  </b>
                  <span>
                    {featured.f.minimal_stream?.length ?? "—"} events in minimal
                    trace
                  </span>
                </motion.div>
                <motion.div
                  className="receipt-print receipt-observed"
                  initial={{ opacity: 0, y: -12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.22, duration: 0.32 }}
                >
                  <div className="receipt-label">Observed</div>
                  <b>
                    {featured.f.explanation ||
                      "Observed ledger differs from the contract"}
                  </b>
                  <span>
                    {featured.f.minimal_stream?.length ?? "—"} events ·{" "}
                    {delta !== null
                      ? formatMoney(delta)
                      : "amount not supplied"}
                  </span>
                  {delta !== null && (
                    <span className="void mini-void">VOID</span>
                  )}
                </motion.div>
              </div>
              <div className="hero-trace">
                {(featured.f.minimal_stream || [])
                  .slice(0, 3)
                  .map((event: any, index: number) => (
                    <motion.div
                      key={`${event.event_id || "event"}-${index}`}
                      className="ticket"
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.35 + index * 0.08 }}
                    >
                      <span>{eventSummary(event)}</span>
                      <span>
                        {typeof event.amount_paise === "number"
                          ? formatMoney(event.amount_paise)
                          : ""}
                      </span>
                    </motion.div>
                  ))}
              </div>
              <span className="source-line">
                {featured.r.candidate?.source === "mutant" ||
                String(featured.r.candidate?.id || "").startsWith("m")
                  ? "HAND-WRITTEN MUTANT — not model output"
                  : String(featured.r.candidate?.id || "").startsWith("x")
                    ? "EXTRA-MUTANT — not model output"
                    : sourceLabel(featured.r.candidate?.source)}
              </span>
            </>
          ) : (
            <DesignedEmpty
              title="No failure record supplied"
              detail="Bundled traces and run records are shown when available."
            />
          )}
        </div>
      </div>
      <section className="status-section">
        <div className="section-head">
          <h2>Readiness ledger</h2>
          <Link className="text-link" to="/status">
            Full status <ArrowRight size={13} />
          </Link>
        </div>
        <StatusBoard items={board as any} />
      </section>
      <div className="proof proof-data">
        {[
          [
            `${citedRuleCount(grounding)}/${Object.keys(grounding?.rules || {}).length || 11}`,
            "rules backed by cited sources",
            "Retrieved empirical evidence from You.com API",
          ],
          [
            `${killed}/${mutants.length}`,
            "mutants killed",
            `${hand.filter((r: any) => r.killed).length} hand-written + ${extra.filter((r: any) => r.killed).length} extra`,
          ],
          [String(runs.length), "runs recorded", "Bundled and indexed records"],
          [
            reproduction.total
              ? `${reproduction.done}/${reproduction.total}`
              : "—",
            "shrinks reproduced",
            "Source-reported reproduction checks",
          ],
          [
            largest === null ? "—" : String(largest),
            "events in largest minimal failing stream",
            "Derived from recorded minimal traces",
          ],
        ].map(([value, label, detail]) => (
          <div className="proof-tile" key={label} title={detail}>
            <strong>{value}</strong>
            <span>{label}</span>
            <small>{detail}</small>
          </div>
        ))}
        <div className="proof-tile hash-tile">
          <strong>
            <CopyChip
              value={specSHA || ""}
              label={specSHA ? `${specSHA.slice(0, 12)}…` : "—"}
            />
          </strong>
          <span>Specification SHA</span>
          <small>Click to copy</small>
        </div>
      </div>
      <EvidenceLanding data={grounding} />
      <Section title="How it works">
        <div className="grid how-grid">
          {[
            ["01 / Contract", "Rules R0–R10 define the formal behavior."],
            [
              "02 / Candidates",
              "Reference, hand-written mutants and model handlers when supplied.",
            ],
            [
              "03 / Attack",
              "Seeded streams probe idempotency, signatures, refunds, types and delivery.",
            ],
            [
              "04 / Shrink & repair",
              "Recorded failures are minimized; a repair needs a full suite re-run.",
            ],
          ].map(([a, b]) => (
            <article className="card" key={a}>
              <div className="eyebrow">{a}</div>
              <p>{b}</p>
            </article>
          ))}
        </div>
      </Section>
      <Section title="Evidence, with limits">
        <div className="card">
          <p>
            Mutants are hand-written. The kill matrix is partly circular and
            self-attested. The specification remains DRAFT-FROZEN. Model pilot
            results appear only when sourced run data exists. No candidate
            ranking is presented.
          </p>
          <div className="row">
            <Badge tone="amber">
              Sandbox gate: {gate?.status || "not supplied"}
            </Badge>
            <Link to="/status" className="btn">
              Full status <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </Section>
      <Section
        title="Recorded failure"
        action={
          <Link to="/kill-matrix" className="btn">
            Open kill matrix
          </Link>
        }
      >
        {featured ? (
          <Link
            id="featured"
            to={`/runs/${featured.r.run_id}/failures/${featured.r.failures.indexOf(featured.f)}`}
            className="card paper featured-paper"
          >
            <div className="eyebrow">
              {featured.f.invariant} / Rule {featured.f.rule}
            </div>
            <h3>{featured.f.explanation}</h3>
            <div className="row">
              <span>
                {featured.f.minimal_stream?.length ?? "—"} events in minimal
                trace
              </span>
              <ClassBadge value={featured.f.classification} />
            </div>
            <Source candidate={featured.r.candidate} />
          </Link>
        ) : (
          <DesignedEmpty
            title="No model pilot finding"
            detail="A curated mutant trace is not a model result."
          />
        )}
      </Section>
      <Section title="Live, cited evidence">
        <EvidencePanel data={grounding} rule="R3" />
      </Section>
      <div className="actions">
        <Link className="btn" to="/break">
          Replay a scenario
        </Link>
        <Link className="btn" to="/pilot">
          Pilot status
        </Link>
        <Link className="btn" to="/method">
          Read the method
        </Link>
      </div>
    </main>
  );
}
function Runs() {
  const { data: runs = [], isLoading } = useData();
  const [all, setAll] = useState(false),
    [q, setQ] = useState(""),
    [source, setSource] = useState("all"),
    [condition, setCondition] = useState("all"),
    [expanded, setExpanded] = useState("");
  const [params] = useSearchParams();
  const ruleFilter = params.get("rule");
  const shown = (all ? runs : latestPerCandidate(runs))
    .filter(
      (r) =>
        (!ruleFilter || r.failures.some((f: any) => f.rule === ruleFilter)) &&
        (r.candidate?.label + " " + r.candidate?.id + " " + r.run_id)
          .toLowerCase()
          .includes(q.toLowerCase()) &&
        (source === "all" || r.candidate?.source === source) &&
        (condition === "all" || r.candidate?.condition === condition),
    )
    .sort((a, b) =>
      String(a.candidate?.id).localeCompare(String(b.candidate?.id)),
    );
  return (
    <main className="page">
      <Title
        eyebrow="Evidence / run explorer"
        title="Findings"
        sub="Run records are evidence, not grades. Default order is alphabetical; repeated runs collapse to the latest per candidate."
      />
      <div className="filters">
        <input
          aria-label="Search candidates or run IDs"
          className="field"
          placeholder="Search candidates or run IDs"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          aria-label="Filter by source"
          className="field"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="all">All sources</option>
          {[
            "reference",
            "mutant",
            "extra-mutant",
            "stub",
            "pre-run",
            "live",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <select
          aria-label="Filter by condition"
          className="field"
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
        >
          <option value="all">All conditions</option>
          <option value="A">A</option>
          <option value="B">B · illustrative</option>
        </select>
        <button className="btn" onClick={() => setAll(!all)}>
          {all ? "Latest per candidate" : "All runs"}
        </button>
        <button className="btn" onClick={() => downloadCsv(shown)}>
          Export CSV
        </button>
      </div>
      {isLoading ? (
        <div className="skeleton" />
      ) : shown.length ? (
        <div className="tablewrap">
          <table className="findings-table" aria-label="Runs and findings table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Source</th>
                <th>Model</th>
                <th>Condition</th>
                <th>Financial failures</th>
                <th>Interface failures</th>
                <th>Minimal trace</th>
                <th>Classification</th>
                <th>Created</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <React.Fragment key={r.run_id}>
                  <tr>
                    <td>
                      <Link to={`/runs/${r.run_id}`}>
                        {r.candidate?.label || r.candidate?.id}
                      </Link>
                    </td>
                    <td>
                      <Source candidate={r.candidate} />
                    </td>
                    <td>{r.candidate?.model || "—"}</td>
                    <td>
                      {r.candidate?.condition === "B"
                        ? "B · illustrative"
                        : r.candidate?.condition || "—"}
                    </td>
                    <td className="failure-count">
                      {
                        r.failures.filter((f: any) => isFinancial(f.invariant))
                          .length
                      }
                    </td>
                    <td className="interface-count">
                      {
                        r.failures.filter((f: any) => !isFinancial(f.invariant))
                          .length
                      }
                    </td>
                    <td>
                      {r.failures.length
                        ? Math.min(
                            ...r.failures.map(
                              (f: any) => f.minimal_stream?.length || 0,
                            ),
                          )
                        : "—"}
                    </td>
                    <td>
                      {r.failures[0]?.classification ? (
                        <ClassBadge value={r.failures[0].classification} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="mono date-nowrap">
                      {formatDate(r.created_at)}
                    </td>
                    <td>
                      <button
                        className="btn compact"
                        aria-expanded={expanded === r.run_id}
                        onClick={() =>
                          setExpanded(expanded === r.run_id ? "" : r.run_id)
                        }
                      >
                        Trace
                      </button>
                    </td>
                  </tr>
                  {expanded === r.run_id && (
                    <tr>
                      <td colSpan={10}>
                        <div className="inline-shrink">
                          <b>
                            {r.candidate?.id} ·{" "}
                            {r.failures[0]?.invariant || "No failure recorded"}
                          </b>
                          {r.failures[0] ? (
                            <ShrinkPlayer
                              original={r.failures[0].original_stream || []}
                              minimal={r.failures[0].minimal_stream || []}
                              history={r.failures[0].shrink_history || []}
                            />
                          ) : (
                            <span>No failing trace in this run.</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <DesignedEmpty
          title="No runs in this view"
          detail="No matching run records are present in the bundled snapshot."
        />
      )}
    </main>
  );
}
function formatDate(value: string) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(date);
}
function downloadCsv(rows: any[]) {
  const keys = [
    "run_id",
    "created_at",
    "candidate.source",
    "candidate.id",
    "candidate.model",
    "candidate.condition",
    "spec_sha",
  ];
  const q = (v: any) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const text = [
    keys.join(","),
    ...rows.map((r) =>
      keys
        .map((k) => q(k.split(".").reduce((x: any, p: string) => x?.[p], r)))
        .join(","),
    ),
  ].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  a.download = "paysift-visible-runs.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}
function RunDetail() {
  const { runId = "" } = useParams();
  const { source } = useApp();
  const {
    data: raw,
    isLoading,
    error,
  } = query("run-" + runId, () => source.getRun(runId));
  const { data: currentSpecHash } = query("current-spec-hash", () =>
    source.getSpecHash(),
  );
  if (isLoading)
    return (
      <main className="page">
        <div className="skeleton" />
      </main>
    );
  if (error || !raw)
    return (
      <main className="page">
        <Empty title="Run unavailable">{String(error)}</Empty>
      </main>
    );
  const r = normalizeRun(raw);
  const invs = invariantKeys(r.results);
  return (
    <main className="page">
      <Title
        eyebrow={`Run / ${r.run_id}`}
        title={r.candidate?.label || r.candidate?.id}
        sub={`Created ${r.created_at || "date not supplied"} · contract ${r.contract_version || "—"}`}
      />
      <Source candidate={r.candidate} />
      <div className="row" style={{ margin: "20px 0" }}>
        <span>run sha</span>
        <Hash value={r.candidate?.sha256} />
        <span>spec</span>
        <Hash value={r.spec_sha} />
        <span>oracle</span>
        <Hash value={r.oracle_sha} />
      </div>
      {r.spec_sha && r.spec_sha !== currentSpecHash && (
        <Badge tone="amber">STALE</Badge>
      )}
      <Section title="Invariant results">
        <div className="scoreboard">
          {invs.map((k) => {
            const x = r.results[k] || {};
            return (
              <div className="score" key={k}>
                <b className={isFinancial(k) ? "red" : "amber"}>{k}</b>
                <span>{isFinancial(k) ? "financial" : "interface"}</span>
                <small>
                  Normal{" "}
                  {x.normal
                    ? `${x.normal.passed}/${x.normal.passed + x.normal.failed}`
                    : "—"}{" "}
                  · Restart{" "}
                  {x.restart
                    ? `${x.restart.passed}/${x.restart.passed + x.restart.failed}`
                    : "—"}
                </small>
              </div>
            );
          })}
        </div>
      </Section>
      <Section title="Concurrency">
        <div className="grid">
          {Object.entries(r.concurrency || {}).map(([k, v]: any) => (
            <div className="card" key={k}>
              <b>{k.replace("_", " ")}</b>
              <p>
                {v.trials ?? 0} trials · {v.failed ?? 0} failures ·{" "}
                {v.warnings ?? 0} warnings
              </p>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Failures">
        {r.failures.length ? (
          r.failures.map((f: any, i: number) => (
            <Link
              to={`/runs/${runId}/failures/${i}`}
              className="card"
              style={{ display: "block", marginBottom: 10 }}
              key={i}
            >
              <div className="row">
                <Badge tone={isFinancial(f.invariant) ? "red" : "amber"}>
                  {f.invariant}
                </Badge>
                <Badge>Rule {f.rule}</Badge>
                <Badge>
                  <ClassBadge value={f.classification} />
                </Badge>
                <span>
                  Seed {f.seed} · first bad step {f.first_bad_step} · minimal{" "}
                  {f.minimal_stream?.length ?? "—"} events
                </span>
                <ArrowRight size={14} />
              </div>
              <p>{f.explanation}</p>
            </Link>
          ))
        ) : (
          <Empty title="All recorded checks passed" />
        )}
      </Section>
      <RawButton data={r} />
    </main>
  );
}
function EvidenceSearch({ rule, data }: { rule: string; data: any }) {
  const { source, mode } = useApp();
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [results, setResults] = useState<any[]>([]);
  const search = async () => {
    if (mode !== "live") return;
    setLoading(true);
    setError("");
    try {
      const payload = await source.searchEvidence(rule);
      const list = Array.isArray(payload?.sources)
        ? payload.sources
        : Array.isArray(payload)
          ? payload
          : [];
      setResults(list);
      if (!list.length)
        setError(
          "No live sources were returned. Showing cached evidence below.",
        );
    } catch (e: any) {
      setError(
        e?.message || "Evidence search failed. Showing cached evidence below.",
      );
    } finally {
      setLoading(false);
    }
  };

  if (mode !== "live") {
    return (
      <div className="evidence-search" style={{ margin: "0.5rem 0 1rem" }}>
        <button
          className="btn"
          disabled
          title="Why is this a bug? search is available only in LIVE API mode. Cached evidence is shown below."
          aria-label="Why is this a bug? (Disabled in static mode)"
        >
          Why is this a bug?
        </button>
      </div>
    );
  }

  return (
    <div className="evidence-search" style={{ margin: "0.5rem 0 1rem" }}>
      <button className="btn" onClick={search} disabled={loading}>
        {loading ? "Searching live evidence…" : "Why is this a bug?"}
      </button>
      {error && (
        <p className="muted" role="status" style={{ marginTop: "0.5rem" }}>
          {error}
        </p>
      )}
      {results.length > 0 && (
        <div className="evidence-sources" style={{ marginTop: "1rem" }}>
          {results.map((src: any, index: number) => (
            <SourceCard key={src.id || src.url || index} source={src} live={true} />
          ))}
        </div>
      )}
    </div>
  );
}

function Failure() {
  const { runId = "", index = "0" } = useParams();
  const { source, mode } = useApp();
  const { data: r } = query("failure-" + runId, () => source.getRun(runId));
  const n = Number(index),
    f = r?.failures?.[n];
  const { data: grounding = null } = useGrounding();
  if (!f)
    return (
      <main className="page">
        <DesignedEmpty
          title="Failure record unavailable"
          detail="No failure record exists at this route."
        />
      </main>
    );
  return (
    <main className="page">
      <div className="eyebrow">
        Failure deep-dive / {f.mode || "normal"} mode
      </div>
      <h1>
        {f.invariant} <em className="red">· Rule {f.rule}</em>
      </h1>
      <p className="lead">{f.explanation}</p>
      <Source candidate={r?.candidate} />
      <div className="row">
        <Badge tone={isFinancial(f.invariant) ? "red" : "amber"}>
          {isFinancial(f.invariant) ? "FINANCIAL" : "INTERFACE"}
        </Badge>
        <ClassBadge value={f.classification} />
        <Badge>
          reproduced {f.repro?.reproduced ?? "—"}/{f.repro?.runs ?? "—"}
        </Badge>
        <span className="spacer" />
        <RawButton data={f} />
      </div>
      {f.mode === "concurrency" ? (
        <DesignedEmpty
          title="Shrink not applicable"
          detail={JSON.stringify(
            f.evidence || "Concurrency evidence not supplied.",
          )}
        />
      ) : (
        <Section title="Shrink player">
          <ShrinkPlayer
            original={f.original_stream || f.shrink_history?.[0] || []}
            minimal={f.minimal_stream || []}
            history={f.shrink_history || []}
          />
          {f.one_minimal && (
            <Badge tone="green">
              1-Minimal: removing any single remaining event removes the failure
            </Badge>
          )}
        </Section>
      )}
      <Section title="Minimal trace">
        <div className="event-timeline">
          {(f.minimal_stream || []).map((e: any, i: number) => (
            <article
              className="step card"
              key={i}
              style={{
                borderColor: i === f.first_bad_step ? "var(--red)" : undefined,
              }}
            >
              <span className="mono">
                {String(i + 1).padStart(2, "0")} / {e.type || "event"}
              </span>
              <p>{eventSummary(e)}</p>
              <span className="source-line">
                event {e.event_id || "—"} · payment {e.payment_id || "—"} ·{" "}
                {e.amount_paise != null
                  ? formatMoney(e.amount_paise)
                  : "amount n/a"}{" "}
                · signature {e.signature?.slice(0, 14) || "n/a"}
              </span>
            </article>
          ))}
        </div>
      </Section>
      <Section title="Ledger: expected vs observed">
        <LedgerDiff failure={f} />
      </Section>
      <Section title="Why is this a bug?">
        <EvidenceSearch data={grounding} rule={f.rule} />
        <EvidencePanel data={grounding} rule={f.rule} defaultOpen={true} />
      </Section>
      <div className="card">
        <div className="void">VOID</div>
        <p>{f.explanation}</p>
        <RuleBadge rule={f.rule} />
        <details>
          <summary>Rule text from the supplied specification</summary>
          <Markdown text={ruleText(specText, f.rule)} />
        </details>
        <p>
          Classification: <ClassBadge value={f.classification} />{" "}
          {f.classification_note || ""}
        </p>
        <div className="actions">
          <Link
            className="btn"
            to={`/break?candidate=${r?.candidate?.id}&scenario=${scenarioForRule(f.rule)}`}
          >
            Break it again
          </Link>
          <Link
            className="btn"
            to={`/repair?candidate=${r?.candidate?.id}&failure=${n}`}
          >
            Ask for a repair
          </Link>
          <button
            className="btn"
            onClick={() =>
              navigator.clipboard?.writeText(
                JSON.stringify(f.minimal_stream, null, 2),
              )
            }
          >
            Copy trace as JSON
          </button>
          <button
            className="btn"
            onClick={() => navigator.clipboard?.writeText(location.href)}
          >
            Copy permalink
          </button>
        </div>
      </div>
    </main>
  );
}
function LedgerDiff({ failure }: any) {
  const delta = moneyDelta(failure);
  const expected = failure?.expected || {},
    observed = failure?.observed || {};
  return (
    <div className="ledger-pair">
      <div className="receipt paper-ledger">
        <div className="eyebrow">What the contract says</div>
        {Object.entries(expected).map(([key, value]: any) => (
          <div className="receipt-row" key={key}>
            <span>{key}</span>
            <span>
              {typeof value === "number" && key.includes("paise")
                ? formatMoney(value)
                : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value)}
            </span>
          </div>
        ))}
      </div>
      <div className="receipt paper-ledger">
        <div className="eyebrow">What the handler did</div>
        {Object.entries(observed).map(([key, value]: any) => (
          <div className="receipt-row" key={key}>
            <span>{key}</span>
            <span>
              {typeof value === "number" && key.includes("paise")
                ? formatMoney(value)
                : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value)}
            </span>
          </div>
        ))}
      </div>
      {delta !== null && (
        <div className="metric-delta">
          <div className="eyebrow">Observed − expected</div>
          <b>{formatMoney(delta)}</b>
          <span>
            Calculated from supplied expected and observed ledger values.
          </span>
        </div>
      )}
    </div>
  );
}
function Rule({ rule }: { rule: string }) {
  return <RuleBadge rule={rule} />;
}
function ruleText(spec: string, id: string) {
  const rule = parseRules(spec).find((item) => item.id === id);
  return rule
    ? `${rule.id} · ${rule.title}\n${rule.body}`
    : "Rule text not supplied.";
}
function scenarioForRule(r: string) {
  return (
    (
      {
        R1: "forged_signature",
        R2: "bool_amount",
        R3: "duplicate_capture",
        R6: "over_refund",
        R8: "rejected_redelivery",
        R9: "restart_between_calls",
      } as any
    )[r] || "duplicate_capture"
  );
}
function KillMatrix() {
  const { source } = useApp();
  const { data: km } = query("matrixpage", () => source.getKillMatrix());
  const rows = km?.rows || [];
  const hand = rows.filter((r: any) => r.source === "mutant"),
    extra = rows.filter((r: any) => r.source === "extra-mutant"),
    mutants = [...hand, ...extra],
    killed = mutants.filter((r: any) => r.killed).length;
  const reference = rows.find((r: any) => r.source === "reference");
  return (
    <main className="page">
      <Title
        eyebrow="Harness validation"
        title="Kill matrix"
        sub="Recorded checks grouped by implementation provenance. This is a partly circular, self-attested harness check."
      />
      <div className="matrix-summary">
        <h2>
          {killed}/{mutants.length} killed
        </h2>
        <p>
          {hand.filter((r: any) => r.killed).length} hand-written +{" "}
          {extra.filter((r: any) => r.killed).length} extra · reference{" "}
          {reference?.killed === false ? "clean" : "status unavailable"}
        </p>
        <span>Counts are calculated from supplied matrix rows.</span>
      </div>
      <Section title="Recorded checks">
        <KillMatrixHeatmap rows={rows} />
      </Section>
      {km && (
        <div className="row">
          <span>oracle_sha</span>
          <Hash value={km.oracle_sha} />
          <span>spec_sha</span>
          <Hash value={km.spec_sha} />
          <RawButton data={km} />
        </div>
      )}
    </main>
  );
}
function BreakPage() {
  const { source, mode } = useApp();
  const { data: sc } = query("scenarios", () => source.getScenarioVerdicts());
  const [params] = useSearchParams();
  const [scenario, setScenario] = useState(
      params.get("scenario") || "duplicate_capture",
    ),
    [candidate, setCandidate] = useState(
      params.get("candidate") || "reference",
    ),
    [result, setResult] = useState<any>(null),
    [err, setErr] = useState("");
  const verdict = sc?.by_candidate?.[candidate]?.[scenario];
  const selected = sc?.scenarios?.[scenario];
  const live = async () => {
    setErr("");
    try {
      setResult(await source.breakIt(candidate, scenario));
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const scenarios = Object.entries(sc?.scenarios || {});
  return (
    <main className="page">
      <Title
        eyebrow="Scenario lab"
        title="Break it"
        sub="Static verdicts replay from the supplied dataset. Live runs require the backend and its sandbox gate."
      />
      <div className="break-layout">
        <aside className="scenario-rail">
          <h2>Scenario</h2>
          <p className="rail-intro">Choose a recorded delivery stream.</p>
          {scenarios.map(([id, x]: any) => (
            <button
              key={id}
              className={`scenario-option ${scenario === id ? "selected" : ""}`}
              onClick={() => {
                setScenario(id);
                setResult(null);
              }}
              aria-pressed={scenario === id}
            >
              <b>{x.title}</b>
              <span>{x.explanation}</span>
              <RuleBadge rule={x.rule} title={x.invariant} />
            </button>
          ))}
        </aside>
        <section className="scenario-result-panel">
          <div className="scenario-toolbar">
            <div>
              <h2>Candidate</h2>
              <p className="rail-intro">
                Reference, mutants or supplied candidates.
              </p>
            </div>
            <select
              className="field"
              aria-label="Select candidate"
              value={candidate}
              onChange={(e) => {
                setCandidate(e.target.value);
                setResult(null);
              }}
            >
              {sc?.candidates?.map((id: string) => (
                <option key={id} value={id}>
                  {id === "reference"
                    ? "Reference"
                    : id.startsWith("m")
                      ? "HAND-WRITTEN MUTANT"
                      : id.startsWith("x")
                        ? "EXTRA-MUTANT"
                        : "Candidate"}{" "}
                  · {id}
                </option>
              ))}
            </select>
            <button
              disabled={mode !== "live"}
              className="btn primary"
              title={
                mode === "live"
                  ? "Run against live API"
                  : "Static snapshot mode: live execution is unavailable"
              }
              onClick={live}
            >
              Run live
            </button>
          </div>
          {mode !== "live" && (
            <div className="unavailable-hint" role="note">
              <CircleHelp size={16} />
              <span>
                <b>Live execution unavailable in static snapshot.</b> Connect
                the configured API and sandbox gate to run this scenario.
              </span>
            </div>
          )}
          {err && (
            <div className="error" role="alert">
              <ShieldAlert /> {err}
            </div>
          )}
          {result || verdict ? (
            <ScenarioResult data={result || verdict} scenario={selected} />
          ) : (
            <DesignedEmpty
              title="No verdict recorded"
              detail="This candidate and scenario pair is not present in the bundled verdict table."
            />
          )}
        </section>
      </div>
      <Section title="Scenario × candidate replay">
        <div className="tablewrap">
          <table aria-label="Scenario candidate replay table">
            <thead>
              <tr>
                <th>Scenario</th>
                {(sc?.candidates || []).map((id: string) => (
                  <th key={id}>{id}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scenarios.map(([id, value]: any) => (
                <tr key={id}>
                  <td>{value.title}</td>
                  {(sc?.candidates || []).map((cid: string) => (
                    <td
                      key={cid}
                      className={
                        sc?.by_candidate?.[cid]?.[id]?.verdict === "pass"
                          ? "green"
                          : "red"
                      }
                    >
                      {sc?.by_candidate?.[cid]?.[id]?.verdict || "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </main>
  );
}
function ScenarioResult({ data, scenario }: any) {
  const expectedLedger = data.expected_ledger || [],
    observedLedger = data.observed_ledger || [];
  const expandPayments = (rows: any[]) =>
    rows.flatMap((row: any) =>
      [
        {
          ...row,
          kind: "captured",
          amount_paise: row.captured_paise,
          event_id: row.payment_id,
        },
        {
          ...row,
          kind: "refunded",
          amount_paise: row.refunded_paise,
          event_id: row.payment_id,
        },
      ].filter((item: any) => typeof item.amount_paise === "number"),
    );
  const expectedPayments = expandPayments(data.expected_payments || []),
    observedPayments = expandPayments(data.observed_payments || []);
  return (
    <article className="scenario-result-card">
      <div className="row">
        <Badge tone={data.verdict === "pass" ? "green" : "red"}>
          {data.verdict || "result"}
        </Badge>
        <span>{scenario?.title || "Scenario result"}</span>
        {scenario?.rule && (
          <RuleBadge rule={scenario.rule} title={scenario.invariant} />
        )}
      </div>
      <p>{data.ledger_diff?.diff_summary || data.failure?.explanation || ""}</p>
      <div className="receipt-pair">
        <LedgerReceipt
          title="Expected ledger"
          rows={expectedLedger}
          counterpart={observedLedger}
          expected
        />
        <LedgerReceipt
          title="Observed ledger"
          rows={observedLedger}
          counterpart={expectedLedger}
        />
      </div>
      {expectedPayments.length + observedPayments.length > 0 && (
        <div className="receipt-pair payment-pair">
          <LedgerReceipt
            title="Expected payments"
            rows={expectedPayments}
            counterpart={observedPayments}
            expected
          />
          <LedgerReceipt
            title="Observed payments"
            rows={observedPayments}
            counterpart={expectedPayments}
          />
        </div>
      )}
      <details className="raw-collapsible">
        <summary>Raw scenario JSON</summary>
        <div className="row">
          <CopyChip value={JSON.stringify(data, null, 2)} label="Copy JSON" />
        </div>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </details>
      <h3>Step verdicts</h3>
      <EventTimeline steps={data.steps || []} />
    </article>
  );
}
function Repair() {
  const { source, mode } = useApp();
  const { data: runs = [] } = useData();
  const { data: status } = query("repair-status", () => source.getStatus());
  const { data: grounding = null } = useGrounding();
  const failures = runs.flatMap((r) =>
    r.failures.map((f: any, index: number) => ({ r, f, index })),
  );
  const best =
    failures.find(
      (x) =>
        ["live", "pre-run"].includes(x.r.candidate?.source) &&
        isFinancial(x.f.invariant),
    ) || failures[0];
  const [chosen, setChosen] = useState(best?.r.candidate?.id || ""),
    [failureId, setFailure] = useState(0),
    [result, setResult] = useState<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!loading) return;
    const t = setInterval(() => setElapsed((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [loading]);
  const selected = failures.find((x) => x.r.candidate?.id === chosen) || best;
  const controller = React.useRef<AbortController | null>(null);
  const run = async () => {
    setLoading(true);
    setElapsed(0);
    setError("");
    controller.current = new AbortController();
    try {
      setResult(
        await source.repair(chosen, failureId, controller.current.signal),
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };
  const blocker = status?.blockers?.find((b: any) =>
    /repair|model|sandbox/i.test(b.title),
  );
  return (
    <main className="page">
      <Title
        eyebrow="Repair loop"
        title="Repair"
        sub="A fix is not accepted on its own terms; the complete suite must run again."
      />
      <div className="repair-flow">
        <PipelineDiagram
          stages={[
            {
              label: "Failure",
              detail: selected?.f?.explanation || "Select a recorded failure.",
              state: selected ? "recorded" : "not run",
              icon: <ShieldAlert size={16} />,
            },
            {
              label: "Prompt",
              detail:
                "Rule text and adapter-sourced evidence are included only when supplied.",
              state: selected ? "ready" : "not run",
              icon: <FileJson size={16} />,
            },
            {
              label: "Fix",
              detail: "A model repair requires a configured live API.",
              state: mode === "live" ? "available" : "blocked",
              icon: <RefreshCw size={16} />,
            },
            {
              label: "Full suite re-run",
              detail: "The repaired candidate must face the full suite.",
              state: result?.suite ? "recorded" : "not run",
              icon: <Activity size={16} />,
            },
            {
              label: "Verdict",
              detail: "Invariant regressions stay visible.",
              state: result ? "recorded" : "not run",
              icon: <Check size={16} />,
            },
          ]}
        />
      </div>
      <div className="row">
        <select
          className="field"
          aria-label="Select candidate"
          value={chosen}
          onChange={(e) => setChosen(e.target.value)}
        >
          {[...new Set(failures.map((x) => x.r.candidate?.id))].map((id) => (
            <option key={id}>{id}</option>
          ))}
        </select>
        <select
          className="field"
          aria-label="Select failure"
          value={failureId}
          onChange={(e) => setFailure(Number(e.target.value))}
        >
          {failures
            .filter((x) => x.r.candidate?.id === chosen)
            .map((x) => (
              <option key={x.index} value={x.index}>
                {x.f.invariant} · Rule {x.f.rule}
              </option>
            ))}
        </select>
        <button
          className="btn primary"
          disabled={loading || mode !== "live" || !selected}
          title={
            mode !== "live"
              ? "Static snapshot mode: a live model repair is unavailable"
              : !selected
                ? "Select a recorded failure"
                : "Send repair request"
          }
          onClick={run}
        >
          Ask the model to fix it
        </button>
        {loading && (
          <button className="btn" onClick={() => controller.current?.abort()}>
            Cancel
          </button>
        )}
      </div>
      {mode !== "live" && (
        <div className="unavailable-hint">
          <CircleHelp size={16} />
          <span>
            <b>Model repair disabled in static snapshot.</b>{" "}
            {blocker?.title ||
              "Connect the live API and sandbox gate to enable it."}
          </span>
        </div>
      )}
      {loading && (
        <div className="card" style={{ marginTop: 18 }}>
          <SkeletonBlock />
          <p>Waiting for backend (live model call) · elapsed {elapsed}s</p>
        </div>
      )}
      {error && <div className="error">{error}</div>}
      {selected && (
        <div className="card selected-failure" style={{ marginTop: 18 }}>
          <div className="eyebrow">Selected recorded failure</div>
          <Source candidate={selected.r.candidate} />
          <p>{selected.f.explanation}</p>
          <RuleBadge rule={selected.f.rule} />
          <EvidencePanel data={grounding} rule={selected.f.rule} />
        </div>
      )}
      {!result && (
        <DesignedEmpty
          title="No repair result recorded"
          detail="This snapshot contains no cached pre-run repair. Nothing here is represented as model output."
        />
      )}
      {result && <RepairResult data={result} />}
    </main>
  );
}
function RepairResult({ data }: any) {
  const before = data.before_code || data.original_code || data.before?.code;
  const after = data.after_code || data.fixed_code || data.after?.code;
  const grounding = useQuery({
    queryKey: ["grounding"],
    queryFn: readGrounding,
  }).data;
  const usedIds = Array.isArray(data.grounding?.source_ids)
    ? data.grounding.source_ids
    : [];
  const directSources = Array.isArray(data.grounding?.sources)
    ? data.grounding.sources
    : [];
  const sourceList = directSources.length
    ? directSources
    : usedIds.length
      ? grounding
        ? Object.values(grounding.rules)
            .flatMap((rule: any) => rule.sources)
            .filter((source: any) => usedIds.includes(source.id))
        : []
      : Array.isArray(data.sources_given_to_model)
        ? data.sources_given_to_model
        : [];
  const beforeInv = data.invariants_before || data.before?.invariants;
  const afterInv = data.invariants_after || data.after?.invariants;
  const broke =
    afterInv &&
    Object.entries(afterInv).some(
      ([key, value]: any) =>
        value?.passed === false && beforeInv?.[key]?.passed !== false,
    );
  return (
    <Section title="Repair result">
      <div className="card">
        <Badge>{data.source || "live"}</Badge>
        {broke && (
          <div className="regression-warning">
            <ShieldAlert size={16} /> Repair regressed another invariant; the
            suite verdict is not a pass.
          </div>
        )}
        <DiffViewer before={before} after={after} />
        {beforeInv && afterInv && (
          <div className="tablewrap">
            <table aria-label="Invariants before and after repair">
              <thead>
                <tr>
                  <th>Invariant</th>
                  <th>Before</th>
                  <th>After</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ...new Set([
                    ...Object.keys(beforeInv),
                    ...Object.keys(afterInv),
                  ]),
                ].map((key: any) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>
                      {String(beforeInv[key]?.passed ?? beforeInv[key] ?? "—")}
                    </td>
                    <td>
                      {String(afterInv[key]?.passed ?? afterInv[key] ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <h3>Sources given to the model</h3>
        {data.grounding?.used === false ? (
          <p className="muted">Repair ran ungrounded</p>
        ) : sourceList.length ? (
          <div className="evidence-sources" style={{ marginTop: "0.5rem" }}>
            {sourceList.map((item: any, i: number) => {
              if (item && typeof item === "object" && item.url) {
                return <SourceCard key={item.id || item.url || i} source={item} />;
              }
              return (
                <div key={i} className="card" style={{ padding: "0.5rem 0.75rem" }}>
                  <span>{item?.title || item?.url || String(item)}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="muted">No source list was supplied with this repair result.</p>
        )}
      </div>
    </Section>
  );
}
function Pilot() {
  const { data: runs = [] } = useData();
  const { source } = useApp();
  const { data: status } = query("pilot-status", () => source.getStatus());
  const selected = runs.filter((r) =>
    ["live", "pre-run"].includes(r.candidate?.source),
  );
  const conditionA = latestPerCandidate(
    selected.filter((r) => r.candidate?.condition === "A" && !r.noncompliant),
  );
  const failures = conditionA.filter((r) =>
    r.failures.some((f: any) => isFinancial(f.invariant)),
  );
  const conditionB = latestPerCandidate(
    selected.filter((r) => r.candidate?.condition === "B"),
  );
  const sorted = [...conditionA].sort((a, b) =>
    String(a.candidate?.id).localeCompare(String(b.candidate?.id)),
  );
  const gates = status?.gates || [],
    blockers = status?.blockers || [];
  const blocked = (rx: RegExp) => blockers.some((x: any) => rx.test(x.title));
  const gate = (id: string) => gates.find((g: any) => g.id === id);
  const steps = [
    {
      label: "Docker",
      state: blocked(/docker/i) ? "blocked" : "not run",
      detail:
        blockers.find((x: any) => /docker/i.test(x.title))?.title ||
        "Host readiness from the status snapshot",
    },
    {
      label: "Keys",
      state: blocked(/model|key/i) ? "blocked" : "not run",
      detail:
        blockers.find((x: any) => /model|key/i.test(x.title))?.title ||
        "Model credentials from the status snapshot",
    },
    {
      label: "Generate",
      state: gate("G4")?.status?.includes("PASSED") ? "ok" : "blocked",
      detail: gate("G4")?.status || "Sandbox status not supplied",
    },
    {
      label: "Pilot",
      state: selected.length ? "ok" : blocked(/pilot/i) ? "blocked" : "not run",
      detail: `${selected.length} sourced model run(s)`,
    },
  ];
  return (
    <main className="page">
      <Title
        eyebrow="Model evaluation / no ranking"
        title="Pilot"
        sub="Candidate outcomes are shown alphabetically. This is not a leaderboard."
      />
      <div className="no-ranking">NO RANKING · alphabetical record order</div>
      {selected.length === 0 ? (
        <>
          <h2 className="pilot-empty-title">No pilot run yet</h2>
          <p className="lead">
            No model-generated live or pre-run candidate is present in the
            supplied snapshot.
          </p>
          <div className="pilot-stepper">
            <PipelineDiagram stages={steps} />
          </div>
        </>
      ) : (
        <>
          <div className="pilot-summary">
            <h2>
              {failures.length} of {conditionA.length} compliant Condition A
              handlers with recorded financial failures
            </h2>
            <p>
              Counts reflect sourced run data only. Condition B is illustrative
              and excluded from this Condition A summary.
            </p>
          </div>
          <Section title="Condition A / sourced runs">
            <div className="pilot-grid">
              {sorted.map((run) => {
                const fails = run.failures.filter((f: any) =>
                  isFinancial(f.invariant),
                );
                return (
                  <article className="card pilot-candidate" key={run.run_id}>
                    <Source candidate={run.candidate} />
                    <Link to={`/runs/${run.run_id}`} className="candidate-run">
                      Open run <ArrowRight size={13} />
                    </Link>
                    <div className="invariant-pass-fail">
                      {invariantKeys(run.results).map((invariant: string) => {
                        const val = run.results[invariant];
                        const fail = Object.values(val || {}).some(
                          (part: any) => Number(part?.failed) > 0,
                        );
                        return (
                          <span
                            key={invariant}
                            className={fail ? "fail-text" : "pass-text"}
                          >
                            {fail ? "FAIL" : "PASS"} · {invariant}
                          </span>
                        );
                      })}
                    </div>
                    <p>
                      Financial failures:{" "}
                      {fails.map((f: any) => f.invariant).join(", ") ||
                        "none recorded"}
                    </p>
                    <p>
                      Minimal trace length:{" "}
                      {run.failures.length
                        ? Math.min(
                            ...run.failures.map(
                              (f: any) => f.minimal_stream?.length || 0,
                            ),
                          )
                        : "—"}
                    </p>
                  </article>
                );
              })}
            </div>
          </Section>
        </>
      )}
      <Section title="Condition B">
        <div className="card">
          <Badge tone="amber">ILLUSTRATIVE</Badge>
          <p>
            {conditionB.length} illustrative run(s) are excluded from the
            Condition A view.
          </p>
        </div>
      </Section>
    </main>
  );
}
function Markdown({ text }: { text: string }) {
  return (
    <div className="card markdown">
      <ReactMarkdown>{DOMPurify.sanitize(text)}</ReactMarkdown>
    </div>
  );
}
function Spec() {
  const { source } = useApp();
  const [specTab, setSpecTab] = useState<"contract" | "gaps">("contract");
  const { data: spec } = query("full-spec", () => source.getSpec());
  const { data: hash } = query("hash", () => source.getSpecHash());
  const { data: grounding = null } = useQuery({
    queryKey: ["grounding"],
    queryFn: () => source.getEvidence(),
  });
  specText = spec || "";
  specHash = hash || "";
  const rules = useMemo(() => parseRules(spec || ""), [spec]);
  const { data: runs = [] } = useData();
  const toc = rules.map((rule: any) => (
    <a href={`#${rule.id.toLowerCase()}`} key={rule.id}>
      {rule.id} · {rule.title}
    </a>
  ));
  const gapCount = grounding
    ? Object.values(grounding.rules).filter((r) =>
        ["PARTIAL", "NOT_FOUND", "CONFLICT"].includes(r.label),
      ).length
    : 0;

  return (
    <main className="page">
      <Title
        eyebrow="Formal contract"
        title="Specification"
        sub="Condition A is the formal contract. Condition B, when present, is illustrative only."
      />
      <div className="row">
        <Badge
          tone={
            spec?.split("\n")[0]?.includes("DRAFT-FROZEN") ? "amber" : "green"
          }
        >
          {spec?.split("\n")[0] || "status unknown"}
        </Badge>
        <Hash value={hash || ""} />
      </div>
      <div className="tabs" role="tablist" aria-label="Specification views" style={{ margin: "1.5rem 0 1rem" }}>
        <button
          className={`btn ${specTab === "contract" ? "primary" : ""}`}
          onClick={() => setSpecTab("contract")}
          role="tab"
          aria-selected={specTab === "contract"}
        >
          Contract Rules
        </button>
        <button
          className={`btn ${specTab === "gaps" ? "primary" : ""}`}
          onClick={() => setSpecTab("gaps")}
          role="tab"
          aria-selected={specTab === "gaps"}
          style={{ marginLeft: "0.5rem" }}
        >
          Spec Gaps ({gapCount})
        </button>
      </div>
      {specTab === "gaps" ? (
        <Section title="Specification gaps & questions for review">
          <p className="lead" style={{ marginBottom: "1rem" }}>
            Rules where public provider documentation is silent or partial. These represent questions for spec review rather than invalidating the contract.
          </p>
          <EvidenceGaps data={grounding} />
        </Section>
      ) : (
        <div className="spec-layout">
          <aside className="spec-toc">
            <b>On this page</b>
            {toc}
          </aside>
          <div className="spec-content">
            <div className="rule-grid">
              {rules.map((rule: any) => {
                const count = runs.reduce(
                  (n: any, run: any) =>
                    n +
                    run.failures.filter((f: any) => f.rule === rule.id).length,
                  0,
                );
                return (
                  <details
                    id={rule.id.toLowerCase()}
                    className="rule-card"
                    key={rule.id}
                  >
                    <summary>
                      <div className="eyebrow">
                        {rule.id} · {rule.title}
                      </div>
                      <span>{rule.body}</span>
                      <small>
                        <Link to={`/runs?rule=${rule.id}`}>
                          Violated in {count} runs <ArrowRight size={12} />
                        </Link>
                      </small>
                    </summary>
                    <div className="rule-full">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {rule.body}
                      </ReactMarkdown>
                      <div style={{ marginTop: "1.25rem" }}>
                        <EvidencePanel data={grounding} rule={rule.id} />
                      </div>
                    </div>
                  </details>
                );
              })}
            </div>
            <Section title="Full supplied contract">
              <div className="markdown full-contract">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h2: ({ children, ...props }: any) => (
                    <h2
                      {...props}
                      id={String(children)
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")}
                    >
                      {children}
                    </h2>
                  ),
                  code: ({ inline, children, className, ...props }: any) => {
                    const language = String(className || "").replace(
                      "language-",
                      "",
                    );
                    return inline ? (
                      <code {...props}>{children}</code>
                    ) : (
                      <div className={`code-block language-${language}`}>
                        <button
                          className="btn copy-code"
                          onClick={() =>
                            navigator.clipboard?.writeText(String(children))
                          }
                        >
                          Copy code
                        </button>
                        <pre>
                          <code {...props}>{children}</code>
                        </pre>
                      </div>
                    );
                  },
                }}
              >
                {spec || ""}
              </ReactMarkdown>
            </div>
          </Section>
        </div>
      </div>
      )}
    </main>
  );
}
function Gaps() {
  const { data } = useQuery({
    queryKey: ["grounding"],
    queryFn: readGrounding,
  });
  return (
    <main className="page">
      <Title
        eyebrow="Evidence / questions for review"
        title="Gaps"
        sub="Rules with partial, missing, conflicting, or convention-marked evidence."
      />
      <EvidenceGaps data={data || null} />
    </main>
  );
}
function Method() {
  const { source } = useApp();
  const { data: status } = query("method-status", () => source.getStatus());
  const gates = status?.gates || [];
  const byId = (id: string) => gates.find((g: any) => g.id === id);
  const stages = [
    {
      label: "Contract",
      detail: "The written rules define the financial behavior under test.",
      state: byId("G1")?.status || "not run",
      icon: <FileJson size={16} />,
    },
    {
      label: "Candidates",
      detail:
        "Reference and hand-written implementations; model handlers only when present.",
      state: byId("G3")?.status || "not run",
      icon: <Database size={16} />,
    },
    {
      label: "Isolated execution",
      detail: "Untrusted handler code must run inside the configured sandbox.",
      state: byId("G4")?.status || "not run",
      icon: <ShieldAlert size={16} />,
    },
    {
      label: "Event streams",
      detail: "Recorded delivery scenarios probe payment edge cases.",
      state: byId("G6")?.status || "not run",
      icon: <Activity size={16} />,
    },
    {
      label: "Ledger oracle",
      detail:
        "Expected and observed payment state are compared after deliveries.",
      state: byId("G8")?.status || "not run",
      icon: <Check size={16} />,
    },
    {
      label: "Shrink",
      detail:
        "The recorded failing stream is reduced without inventing intermediate events.",
      state: byId("G7")?.status || "not run",
      icon: <ArrowDownRight size={16} />,
    },
    {
      label: "Repair and re-run",
      detail: "A repair needs the full suite to run again before a verdict.",
      state:
        status?.blockers?.find((x: any) => /repair/i.test(x.title))?.title ||
        "not run",
      icon: <RefreshCw size={16} />,
    },
    {
      label: "Matrix",
      detail:
        "Reference cleanliness and intended mutant failures remain visible.",
      state: byId("G3")?.status || "not run",
      icon: <Filter size={16} />,
    },
  ];
  return (
    <main className="page">
      <Title
        eyebrow="Method / evidence pipeline"
        title="From contract to counterexample"
        sub="A deterministic oracle checks ledger state after each delivery. Shrinking isolates the smallest recorded trace that continues to fail."
      />
      <PipelineDiagram stages={stages} />
      <Section
        title="Questions for review"
        action={
          <Link className="btn" to="/gaps">
            Open gaps
          </Link>
        }
      >
        <EvidenceGaps
          data={
            useQuery({ queryKey: ["grounding"], queryFn: readGrounding })
              .data || null
          }
        />
      </Section>
      <Section title="Honest limits">
        <div className="card">
          <p>
            The mutant suite is hand-written; the matrix is partly circular and
            self-attested. The specification remains DRAFT-FROZEN pending human
            review. No model pilot finding is implied by mutant results. No
            ranking is shown.
          </p>
        </div>
      </Section>
    </main>
  );
}
function Demo() {
  const { source } = useApp();
  const [beat, setBeat] = useState(0);
  const [notes, setNotes] = useState(false);
  const { data: grounding = null } = useQuery({
    queryKey: ["grounding"],
    queryFn: () => source.getEvidence(),
  });
  const hasGrounding = !!(grounding && Object.keys(grounding.rules || {}).length > 0);
  const beats = useMemo(() => {
    const list = [
      "The claim",
      "Harness trust",
      "The finding",
      "Shrink",
      "Break it",
    ];
    if (hasGrounding) {
      list.push("Evidence grounding");
    }
    list.push("Repair", "Honest limits");
    return list;
  }, [hasGrounding]);

  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setBeat((x) => Math.min(beats.length - 1, x + 1));
      if (e.key === "ArrowLeft") setBeat((x) => Math.max(0, x - 1));
      if (e.key.toLowerCase() === "n") setNotes((v) => !v);
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [beats.length]);

  return (
    <main className="page">
      <div className="row">
        <Badge>
          GUIDED PITCH / {beat + 1} OF {beats.length}
        </Badge>
        <span className="spacer" />
        <span className="keyhint">← → navigate</span>
      </div>
      <h1 style={{ minHeight: 150 }}>{beats[beat]}</h1>
      <div className="card">
        <DemoBeat name={beats[beat]} grounding={grounding} />
      </div>
      <div className="actions">
        <button className="btn" onClick={() => setBeat(Math.max(0, beat - 1))}>
          Previous
        </button>
        <button
          className="btn primary"
          onClick={() => setBeat(Math.min(beats.length - 1, beat + 1))}
        >
          Next <ArrowRight size={14} />
        </button>
        <Link className="btn" to="/">
          Exit
        </Link>
      </div>
      <button className="btn" onClick={() => setNotes((v) => !v)}>
        N · {notes ? "Hide" : "Show"} speaker notes
      </button>
      {notes && (
        <div className="card">
          <b>Speaker notes</b>
          <p>
            {(() => {
              const current = beats[beat];
              if (current === "The claim") return "PaySift tests webhook handlers against a written financial contract.";
              if (current === "Harness trust") return "Reference and mutant checks are not independent proof; state that limitation.";
              if (current === "The finding") return "Only sourced findings are eligible; no model pilot exists in this snapshot.";
              if (current === "Shrink") return "The shrink trace is derived from recorded failure data.";
              if (current === "Break it") return "Static replay is not the same as a live sandbox execution.";
              if (current === "Evidence grounding") return "Provider documentation grounds the rule: empirical evidence shows where industry standards require idempotency, and where PaySift internal conventions apply.";
              if (current === "Repair") return "No cached model repair is bundled.";
              return "Spec is draft-frozen; model outcomes are not ranked.";
            })()}
          </p>
        </div>
      )}
    </main>
  );
}
function DemoBeat({ name, grounding }: { name: string; grounding: any }) {
  if (name === "Harness trust") return <KillMatrix />;
  if (name === "The finding" || name === "Shrink") return <Runs />;
  if (name === "Break it") return <BreakPage />;
  if (name === "Evidence grounding")
    return (
      <div className="demo-evidence">
        <p className="lead" style={{ marginBottom: "1rem" }}>
          Empirical documentation from payment gateways grounds the contract rules. Quotes are verified verbatim substrings.
        </p>
        <EvidencePanel data={grounding} rule="R3" defaultOpen={true} />
      </div>
    );
  if (name === "Repair") return <Repair />;
  if (name === "Honest limits") return <Status />;
  return (
    <p>
      Contract → event stream → deterministic ledger oracle → minimized
      counterexample. No ranking; only reproducible evidence.
    </p>
  );
}
function Status() {
  const { source, mode } = useApp();
  const { data: health } = query("health", () => source.health());
  const { data: s } = query("statics", () => source.getStatus());
  const { data: runs = [] } = useData();
  const gates = s?.gates || [];
  return (
    <main className="page">
      <Title eyebrow="Runtime and blockers" title="Status" />
      <div className="grid">
        <div className="card">
          <div className="eyebrow">API</div>
          <DataStatus />
          <p>
            {mode === "live"
              ? health?.status || "API is reachable"
              : "Static snapshot active; no API health probe was made."}
          </p>
        </div>
        <div className="card">
          <div className="eyebrow">Contract</div>
          <p>Spec {specHash.slice(0, 12) || "—"}</p>
          <p>Oracle {runs[0]?.oracle_sha?.slice(0, 12) || "—"}</p>
        </div>
        <div className="card">
          <div className="eyebrow">Dataset</div>
          <p>{runs.length} bundled/indexed runs</p>
          <p>{s?.generated_at || "snapshot time not recorded"}</p>
        </div>
      </div>
      <Section title="Gate status">
        <div className="grid">
          {gates.map((g: any) => (
            <div className="card" key={g.id}>
              <b>
                {g.id} · {g.title}
              </b>
              <p
                className={
                  g.status.includes("BLOCK")
                    ? "amber"
                    : g.status.includes("PASSED")
                      ? "green"
                      : "muted"
                }
              >
                {g.status}
              </p>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Open human items">
        <Markdown
          text={
            (s?.blockers || [])
              .map((b: any) => `- **${b.id} · ${b.severity} · ${b.title}**`)
              .join("\n") ||
            "See the supplied NEEDS_HUMAN.md for recorded blockers."
          }
        />
      </Section>
      <div className="actions">
        <Link to="/gaps" className="btn">
          Questions for review
        </Link>
        <Link to="/dev/contract" className="btn">
          Contract diagnostics
        </Link>
      </div>
    </main>
  );
}
function DevContract() {
  const { data: status } = query("dev-status", () => staticSource.getStatus());
  const { data: ix = [] } = query("idx", () => staticSource.listRuns());
  return (
    <main className="page">
      <Title eyebrow="Hidden developer route" title="Contract diagnostics" />
      <div className="card">
        <b>Bundled contract presence</b>
        <p>
          Run schema, spec, hash, matrix, scenarios and status are served from
          public/data.
        </p>
        <p>
          Local run files present: {ix.length}. API URL: {apiBase}
        </p>
        <p>
          Live endpoint checks: run `npm run check:api` with the backend
          available.
        </p>
        <pre>{JSON.stringify(status, null, 2)}</pre>
        <button
          className="btn"
          onClick={() =>
            navigator.clipboard?.writeText(
              JSON.stringify({ apiBase, runFiles: ix.length, status }, null, 2),
            )
          }
        >
          Copy report
        </button>
      </div>
    </main>
  );
}
function Samples() {
  const [data, setData] = useState<any[]>([]);
  useEffect(() => {
    Promise.all(
      ["sample.json", "kill_matrix.sample.json"].map((f) =>
        fetch(`/data/${f}`)
          .then((r) => r.json())
          .catch(() => null),
      ),
    ).then(setData);
  }, []);
  return (
    <main className="page">
      <Title eyebrow="Hidden developer gallery" title="Sample files" />
      <Badge tone="red">FAKE SAMPLE</Badge>
      {data.map((x, i) => (
        <div className="card" key={i} style={{ marginTop: 12 }}>
          <Badge tone="red">FAKE SAMPLE</Badge>
          <pre>{JSON.stringify(x, null, 2)}</pre>
        </div>
      ))}
    </main>
  );
}
function NotFound() {
  return (
    <main className="page">
      <Title eyebrow="404" title="This route is not in the ledger." />
      <Link to="/" className="btn">
        Return to findings
      </Link>
    </main>
  );
}
const appRootContainer = document.getElementById("root")!;
const windowWithRoot = window as any;
if (!windowWithRoot.__paysiftReactRoot)
  windowWithRoot.__paysiftReactRoot = createRoot(appRootContainer);
const appRoot = windowWithRoot.__paysiftReactRoot;
appRoot.render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
