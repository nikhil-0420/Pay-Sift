import React, { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Check,
  CircleHelp,
  Copy,
  Pause,
  Play,
  SkipBack,
  SkipForward,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  alignSubsequence,
  eventSummary,
  formatMoney,
  invariantKeys,
} from "./lib/helpers";
import {
  citedRuleCount,
  type GroundingData,
  type GroundingSource,
  type EvidenceLabel,
} from "./data/grounding";

export function CopyChip({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button
      type="button"
      className="copy-chip"
      onClick={copy}
      title={`Copy ${label || "value"}`}
      aria-label={`Copy ${label || value}`}
    >
      <span>
        {label || `${value.slice(0, 12)}${value.length > 12 ? "…" : ""}`}
      </span>
      <Copy size={12} />
      <span className="copy-toast" role="status">
        {copied ? "Copied" : ""}
      </span>
    </button>
  );
}

export function RuleBadge({
  rule,
  title = "",
}: {
  rule: string;
  title?: string;
}) {
  return (
    <Link
      to={`/spec#${rule.toLowerCase()}`}
      className="rule-badge"
      title={title || `Open specification ${rule}`}
    >
      <span>{rule}</span>
      <span className="rule-popover">
        {title || "Open the supplied rule text"}
        <ArrowRight size={12} />
      </span>
    </Link>
  );
}

export function StatusBoard({
  items,
}: {
  items: Array<{
    label: string;
    state: "ok" | "blocked" | "not run";
    detail?: string;
  }>;
}) {
  const icon = {
    ok: <Check size={13} />,
    blocked: <CircleHelp size={13} />,
    "not run": <CircleHelp size={13} />,
  };
  return (
    <div className="status-board" aria-label="System readiness">
      {items.map((item) => (
        <div
          className={`status-chip state-${item.state.replace(" ", "-")}`}
          key={item.label}
          title={item.detail || item.state}
        >
          {icon[item.state]}
          <span>{item.label}</span>
          <b>{item.state}</b>
        </div>
      ))}
    </div>
  );
}

export function DesignedEmpty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="designed-empty">
      <div className="empty-stamp">NO RECORD</div>
      <div>
        <div className="eyebrow">Nothing recorded here</div>
        <h3>{title}</h3>
        <p>{detail}</p>
        {action}
      </div>
    </div>
  );
}

export function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-block" aria-label="Loading">
      <span />
      <span />
      <span style={{ width: `${Math.max(40, 100 - lines * 9)}%` }} />
    </div>
  );
}

export function ShrinkPlayer({
  original = [],
  minimal = [],
  history = [],
}: {
  original?: any[];
  minimal?: any[];
  history?: any[][];
}) {
  const reduced = useReducedMotion();
  const frames: any[][] =
    history.length > 1
      ? history
      : [original, minimal].filter((frame) => frame.length > 0);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing || frames.length < 2) return;
    const timer = window.setInterval(
      () =>
        setFrame((n) => {
          if (n + 1 >= frames.length) {
            setPlaying(false);
            return n;
          }
          return n + 1;
        }),
      900 / speed,
    );
    return () => window.clearInterval(timer);
  }, [playing, frames.length, speed]);
  const current = frames[frame] || minimal;
  let removed: any[] = [];
  if (frame > 0 && frames[frame - 1] && current) {
    try {
      removed = alignSubsequence(frames[frame - 1], current).removed.map(
        (i) => frames[frame - 1][i],
      );
    } catch {
      removed = [];
    }
  }
  const minimalKeys = new Set(
    minimal.map(
      (event) =>
        `${event?.event_id || ""}:${event?.tag || ""}:${event?.amount_paise || ""}`,
    ),
  );
  return (
    <div className="shrink-player">
      <div
        className="shrink-controls"
        role="group"
        aria-label="Shrink trace controls"
      >
        <button
          className="btn"
          onClick={() => setPlaying((value) => !value)}
          aria-label={
            playing ? "Pause shrink playback" : "Play shrink playback"
          }
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}{" "}
          {playing ? "Pause" : "Play"}
        </button>
        <button
          className="btn"
          onClick={() => setFrame((n) => Math.max(0, n - 1))}
          aria-label="Previous shrink step"
        >
          <SkipBack size={14} />
        </button>
        <input
          aria-label="Shrink step"
          type="range"
          min="0"
          max={Math.max(0, frames.length - 1)}
          value={frame}
          onChange={(event) => setFrame(Number(event.target.value))}
        />
        <button
          className="btn"
          onClick={() => setFrame((n) => Math.min(frames.length - 1, n + 1))}
          aria-label="Next shrink step"
        >
          <SkipForward size={14} />
        </button>
        <select
          className="field speed-select"
          value={speed}
          onChange={(event) => setSpeed(Number(event.target.value))}
          aria-label="Playback speed"
        >
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
        </select>
        <span className="mono">
          {frames.length ? `${frame + 1} / ${frames.length}` : "Trace only"}
        </span>
      </div>
      <div className="shrink-events" aria-live="polite">
        <AnimatePresence initial={false}>
          {current.map((event, index) => {
            const key = `${event?.event_id || ""}:${event?.tag || ""}:${event?.amount_paise || ""}`;
            const isRemoved = minimal.length > 0 && !minimalKeys.has(key);
            return (
              <motion.div
                key={`${key}:${index}`}
                className={`ticket ${isRemoved ? "removed-event" : ""}`}
                initial={reduced ? false : { opacity: 0, y: -5 }}
                animate={{ opacity: isRemoved ? 0.45 : 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: reduced ? 0 : 0.18 }}
              >
                <span>{eventSummary(event)}</span>
                <span>
                  {typeof event?.amount_paise === "number"
                    ? formatMoney(event.amount_paise)
                    : ""}
                </span>
                {isRemoved && <b>removed by shrinker</b>}
              </motion.div>
            );
          })}
        </AnimatePresence>
        {removed.map((event, index) => (
          <div
            className="removed-note"
            key={`removed-${event?.event_id || index}`}
          >
            − {eventSummary(event)} · removed by shrinker
          </div>
        ))}
        {!current.length && (
          <span className="muted">No trace data supplied.</span>
        )}
      </div>
    </div>
  );
}

export function EventTimeline({ steps = [] }: { steps?: any[] }) {
  if (!steps.length)
    return (
      <DesignedEmpty
        title="No step verdicts supplied"
        detail="This replay contains no step-by-step verdict records."
      />
    );
  return (
    <div className="event-timeline">
      {steps.map((step, index) => (
        <details className="event-step" key={step.step_index ?? index} open>
          <summary>
            <span className="timeline-index">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span>{step.tag || step.event_id || `Step ${index + 1}`}</span>
            <b
              className={
                step.expected_status === step.observed_status
                  ? "pass-text"
                  : "fail-text"
              }
            >
              {step.observed_status || "status not supplied"}
            </b>
          </summary>
          <div className="event-step-body">
            <span>Expected: {step.expected_status || "—"}</span>
            <span>Observed: {step.observed_status || "—"}</span>
            {step.explanation && <p>{step.explanation}</p>}
          </div>
        </details>
      ))}
    </div>
  );
}

export function LedgerReceipt({
  title,
  rows = [],
  counterpart = [],
  expected = false,
}: {
  title: string;
  rows?: any[];
  counterpart?: any[];
  expected?: boolean;
}) {
  const otherCounts = new Map(
    counterpart.map((row) => [
      ledgerKey(row),
      counterpart.filter((candidate) => ledgerKey(candidate) === ledgerKey(row))
        .length,
    ]),
  );
  const seen = new Map<string, number>();
  return (
    <section className="ledger-receipt">
      <div className="receipt-heading">
        <span>{title}</span>
        <b>{expected ? "EXPECTED" : "OBSERVED"}</b>
      </div>
      {rows.length ? (
        <div className="ledger-scroll">
          <table className="ledger-table" aria-label="Ledger transactions">
            <thead>
              <tr>
                <th>Entry</th>
                <th>Kind</th>
                <th>₹ Amount</th>
                <th>Event ID</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const key = ledgerKey(row);
                const count = (seen.get(key) || 0) + 1;
                seen.set(key, count);
                const isExtra =
                  !otherCounts.has(key) || count > (otherCounts.get(key) || 0);
                return (
                  <tr
                    key={`${key}:${index}`}
                    className={isExtra ? "ledger-delta" : ""}
                  >
                    <td>{row.entry_id ?? row.payment_id ?? index + 1}</td>
                    <td>{row.kind || row.type || "—"}</td>
                    <td>
                      {typeof row.amount_paise === "number"
                        ? formatMoney(row.amount_paise)
                        : "—"}
                    </td>
                    <td>{row.event_id || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="ledger-none">No ledger entries supplied</div>
      )}
    </section>
  );
}
function ledgerKey(row: any) {
  return `${row?.payment_id || ""}|${row?.kind || row?.type || ""}|${row?.amount_paise ?? ""}|${row?.event_id || ""}`;
}

export function EvidenceChip({
  live = false,
  date,
}: {
  live?: boolean;
  date?: string;
}) {
  return (
    <span className={`evidence-chip ${live ? "chip-live" : "chip-cached"}`}>
      {live ? "LIVE" : "CACHED"}{date ? ` · ${date}` : ""}
    </span>
  );
}

export function SourceCard({
  source,
  live = false,
}: {
  source: GroundingSource;
  live?: boolean;
}) {
  const date = source.retrieved_at
    ? new Date(source.retrieved_at).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : undefined;
  return (
    <a
      className="evidence-source"
      key={source.id}
      href={source.url}
      target="_blank"
      rel="noreferrer"
      aria-label={`${source.title} (${source.domain})`}
    >
      <div className="source-meta-row">
        <span className="eyebrow">{source.domain}</span>
        <EvidenceChip live={live} date={date} />
      </div>
      <b>{source.title}</b>
      {source.snippet && <span className="source-snippet">{source.snippet}</span>}
      <span className="outbound">Open source ↗</span>
    </a>
  );
}

export function EvidencePanel({
  data,
  rule,
  defaultOpen = false,
}: {
  data: GroundingData | null;
  rule: string;
  defaultOpen?: boolean;
}) {
  const item = data?.rules[rule];
  if (!data || !item)
    return <div className="evidence-empty">Evidence not retrieved yet</div>;
  const sourceDate =
    item.sources
      .map((source) => source.retrieved_at)
      .filter(Boolean)
      .sort()
      .at(-1) || data?.generated_at;
  const date = sourceDate
    ? new Date(sourceDate).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "date not supplied";
  const topSources = item.sources.slice(0, 3);
  return (
    <details className="evidence-panel" open={defaultOpen}>
      <summary>
        <span>Evidence for {rule}</span>
        <b className={`evidence-label label-${item.label.toLowerCase()}`}>
          {item.label}
        </b>
        <EvidenceChip live={false} date={date} />
      </summary>
      <div className="evidence-meta">
        {item.convention && (
          <span className="convention-tag">PaySift convention</span>
        )}
        <span className="review-state">
          {item.human_reviewed ? "human-reviewed" : "LLM-judged, unreviewed"}
        </span>
      </div>
      <p className="evidence-wording">
        {item.label === "NOT_FOUND"
          ? `sources retrieved, none support this rule (retrieved ${date})`
          : `supporting sources, retrieved ${date}.`}
      </p>
      {item.quote && (
        <blockquote className="evidence-quote">“{item.quote}”</blockquote>
      )}
      {item.reason && (
        <p className="evidence-reason">
          <b>Reason:</b> {item.reason}
        </p>
      )}
      {topSources.length ? (
        <div className="evidence-sources">
          {topSources.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </div>
      ) : (
        <p className="evidence-empty muted">No source found</p>
      )}
    </details>
  );
}

export function EvidenceLanding({
  data,
  featuredRule = "R8",
}: {
  data: GroundingData | null;
  featuredRule?: string;
}) {
  if (!data)
    return (
      <div className="evidence-landing card">
        <div className="evidence-empty">Evidence not retrieved yet</div>
      </div>
    );
  const targetRule =
    featuredRule ||
    Object.keys(data.rules).find((r) => data.rules[r].sources.length > 0) ||
    "R8";

  const labels = Object.values(data.rules || {}).map((r) => r.label);
  const supported = labels.filter((l) => l === "SUPPORTED").length;
  const partial = labels.filter((l) => l === "PARTIAL").length;
  const notFound = labels.filter((l) => l === "NOT_FOUND").length;

  return (
    <section className="evidence-landing-section">
      <div className="section-head">
        <div>
          <div className="eyebrow">Documentation grounding</div>
          <h2>Live, cited evidence</h2>
        </div>
        <Link className="text-link" to="/gaps">
          View spec gaps <ArrowRight size={13} />
        </Link>
      </div>
      <div className="evidence-landing card">
        <div className="evidence-landing-stat">
          <strong>
            {supported} supported, {partial} partial, {notFound} not found
          </strong>
          <p className="lead">
            Empirical documentation retrieved via search and evaluated against formal contract rules.
          </p>
        </div>
        <div className="evidence-landing-preview">
          <EvidencePanel data={data} rule={targetRule} defaultOpen={true} />
        </div>
      </div>
    </section>
  );
}

export function EvidenceGaps({ data }: { data: GroundingData | null }) {
  if (!data)
    return (
      <DesignedEmpty
        title="Evidence not retrieved yet"
        detail="No grounding records are available to review."
      />
    );
  const gaps = Object.entries(data.rules).filter(
    ([, value]) =>
      ["PARTIAL", "NOT_FOUND", "CONFLICT"].includes(value.label) ||
      value.convention,
  );
  if (!gaps.length)
    return (
      <DesignedEmpty
        title="No questions for review"
        detail="No partial, missing, conflicting, or convention-marked evidence is present."
      />
    );
  return (
    <div className="tablewrap">
      <table aria-label="Specification gap questions">
        <thead>
          <tr>
            <th>Rule</th>
            <th>Label</th>
            <th>Reason</th>
            <th>Sources</th>
            <th>Review</th>
          </tr>
        </thead>
        <tbody>
          {gaps.map(([rule, value]) => (
            <tr key={rule}>
              <td>
                <RuleBadge rule={rule} />
              </td>
              <td>
                <span
                  className={`evidence-label label-${value.label.toLowerCase()}`}
                >
                  {value.label}
                </span>
              </td>
              <td>{value.reason || "Review the available source coverage."}</td>
              <td>{value.sources.length}</td>
              <td>
                <Link to={`/spec#${rule.toLowerCase()}`}>Open {rule} ↗</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DiffViewer({
  before,
  after,
}: {
  before?: string;
  after?: string;
}) {
  if (typeof before !== "string" || typeof after !== "string")
    return (
      <DesignedEmpty
        title="Diff not available"
        detail="Before-and-after source code is shown only when a repair result supplies both versions."
      />
    );
  const left = before.split("\n");
  const right = after.split("\n");
  return (
    <div className="diff-viewer">
      <section>
        <header>Before</header>
        <pre>
          {left.map((line, index) => (
            <span key={index}>
              {String(index + 1).padStart(3, "0")} {line}
              {"\n"}
            </span>
          ))}
        </pre>
      </section>
      <section>
        <header>After</header>
        <pre>
          {right.map((line, index) => (
            <span key={index}>
              {String(index + 1).padStart(3, "0")} {line}
              {"\n"}
            </span>
          ))}
        </pre>
      </section>
    </div>
  );
}

export function PipelineDiagram({
  stages,
}: {
  stages: Array<{
    label: string;
    detail: string;
    state: string;
    icon?: React.ReactNode;
  }>;
}) {
  const reduced = useReducedMotion();
  const stateTone = (state: string) => {
    const value = String(state || "").toLowerCase();
    if (/block|fail|unavailable|error/.test(value)) return "blocked";
    if (/pending|ready|available|review/.test(value)) return "pending";
    if (/pass|recorded|complete|^ok$|clean/.test(value)) return "complete";
    return "idle";
  };
  return (
    <div className={`pipeline pipeline-${stages.length}`} aria-label="Process flow">
      {stages.map((stage, index) => {
        const tone = stateTone(stage.state);
        return (
          <motion.article
            className="pipeline-stage"
            key={stage.label}
            data-state={tone}
            initial={reduced ? false : { opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.25 }}
            transition={{
              duration: reduced ? 0 : 0.28,
              delay: reduced ? 0 : index * 0.035,
            }}
          >
            <div className="pipeline-node" aria-hidden="true">
              {stage.icon || String(index + 1).padStart(2, "0")}
              <span className="pipeline-index">{String(index + 1).padStart(2, "0")}</span>
            </div>
            <div className="pipeline-copy">
              <div className="pipeline-topline">
                <b>{stage.label}</b>
                <span className={`state-pill state-${tone}`} title={stage.state}>{stage.state}</span>
              </div>
              <p>{stage.detail}</p>
            </div>
          </motion.article>
        );
      })}
    </div>
  );
}

export function KillMatrixHeatmap({ rows }: { rows: any[] }) {
  const all = rows || [];
  const invariants = invariantKeys(
    all.find((row) => row.results)?.results || {},
  );
  const groups = [
    { key: "reference", title: "Reference" },
    { key: "mutant", title: "Hand-written" },
    { key: "extra-mutant", title: "Extra" },
  ];
  const cell = (row: any, invariant: string) =>
    row?.results?.[invariant]?.normal;
  return (
    <div className="heatmap-scroll">
      <table className="heatmap-table" aria-label="Mutant kill matrix heatmap">
        <thead>
          <tr>
            <th className="sticky-first">Candidate</th>
            <th>Expected rule</th>
            {invariants.map((invariant) => (
              <th key={invariant}>{invariant}</th>
            ))}
            <th>Rules hit</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const groupRows = all.filter((row) => row.source === group.key);
            if (!groupRows.length) return null;
            return (
              <React.Fragment key={group.key}>
                <tr className="heatmap-group">
                  <th colSpan={invariants.length + 3}>
                    {group.title} · {groupRows.length}
                  </th>
                </tr>
                {groupRows.map((row, index) => (
                  <motion.tr
                    key={row.id}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.025 }}
                  >
                    <th className="sticky-first" title={row.notes || row.label}>
                      <b>{row.id}</b>
                      <small>{row.label}</small>
                    </th>
                    <td>{row.expected_rule || "—"}</td>
                    {invariants.map((invariant) => {
                      const result = cell(row, invariant);
                      const failed = Number(result?.failed || 0);
                      const applicable = !!result;
                      return (
                        <td
                          key={invariant}
                          className={`heat-cell ${applicable ? (failed ? "heat-fail" : "heat-pass") : "heat-na"} ${row.expected_invariant === invariant ? "intended-rule" : ""}`}
                          title={`${invariant}: ${applicable ? `${failed} failed of ${Number(result.passed || 0) + failed} checks` : "not applicable"}${row.rules_hit?.length ? ` · rules hit: ${row.rules_hit.join(", ")}` : ""}${row.notes ? ` · ${row.notes}` : ""}`}
                        >
                          {applicable ? `${failed} fail` : "—"}
                          {row.expected_invariant === invariant && (
                            <span aria-label="intended invariant">
                              {" "}
                              · intended
                            </span>
                          )}
                        </td>
                      );
                    })}
                    <td>{row.rules_hit?.join(", ") || "—"}</td>
                  </motion.tr>
                ))}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
      <div className="heatmap-legend">
        <span>— Not applicable</span>
        <span className="legend-pass">0 fail · recorded checks pass</span>
        <span className="legend-fail">Recorded failures</span>
        <span>Outline · intended invariant</span>
      </div>
    </div>
  );
}
