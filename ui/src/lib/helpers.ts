export const isFinancial = (k: string) => {
  const m = k.match(/^I(\d)_?(.*)$/);
  return !!m && Number(m[1]) <= 4;
};
export const invariantKeys = (obj: Record<string, unknown>) =>
  Object.keys(obj || {}).sort(
    (a, b) =>
      Number(a.match(/^I(\d)/)?.[1] || 99) -
      Number(b.match(/^I(\d)/)?.[1] || 99),
  );
export const formatMoney = (paise: number) => {
  const rupees = Math.trunc(paise / 100);
  const sign = paise < 0 ? "-" : "";
  const n = Math.abs(rupees).toLocaleString("en-IN");
  const cents = Math.abs(paise) % 100;
  return `₹${sign}${n}${cents ? "." + String(cents).padStart(2, "0") : ""}`;
};
export const moneyDelta = (f: any): number | null => {
  const e = f?.expected,
    o = f?.observed;
  if (!e || !o) return null;
  const read = (x: any): number | undefined => {
    for (const key of [
      "balance_paise",
      "total_paise",
      "net_paise",
      "balance",
      "total",
    ])
      if (typeof x[key] === "number") return x[key];
    if (Array.isArray(x.payments))
      return x.payments.reduce(
        (s: number, p: any) =>
          s + (Number(p.captured_paise) || 0) - (Number(p.refunded_paise) || 0),
        0,
      );
    return undefined;
  };
  const a = read(e),
    b = read(o);
  return a === undefined || b === undefined ? null : b - a;
};
export const eventSummary = (e: any) =>
  e?.summary ||
  [
    e?.type,
    e?.event_id,
    e?.payment_id,
    typeof e?.amount_paise === "number" ? formatMoney(e.amount_paise) : "",
  ]
    .filter(Boolean)
    .join(" · ") ||
  "Event";
const key = (e: any) => `${e?.raw_body_b64 || ""}\u0000${e?.signature || ""}`;
export function alignSubsequence(previous: any[], next: any[]) {
  const positions: number[] = [];
  let j = 0;
  for (let i = 0; i < previous.length && j < next.length; i++)
    if (key(previous[i]) === key(next[j])) {
      positions.push(i);
      j++;
    }
  if (j !== next.length)
    throw new Error(
      "Shrink history step is not a subsequence of the previous step.",
    );
  return {
    survivors: positions,
    removed: previous.map((_, i) => i).filter((i) => !positions.includes(i)),
  };
}
export function normalizeRun(raw: any) {
  const x = raw && typeof raw === "object" ? raw : {};
  return {
    ...x,
    run_id: String(x.run_id || x.id || "unknown"),
    candidate:
      x.candidate && typeof x.candidate === "object" ? x.candidate : {},
    results: x.results && typeof x.results === "object" ? x.results : {},
    failures: Array.isArray(x.failures) ? x.failures : [],
    concurrency:
      x.concurrency && typeof x.concurrency === "object" ? x.concurrency : {},
    spec_sha: String(x.spec_sha || ""),
  };
}
export function sourceLabel(src: string) {
  return src === "mutant"
    ? "HAND-WRITTEN MUTANT"
    : src === "extra-mutant"
      ? "EXTRA-MUTANT"
      : src === "reference"
        ? "REFERENCE"
        : src === "live" || src === "pre-run" || src === "model"
          ? "MODEL"
          : (src || "unknown").toUpperCase();
}
export function latestPerCandidate(runs: any[]) {
  const map = new Map<string, any>();
  for (const r of [...runs].sort((a, b) =>
    String(b.created_at || "").localeCompare(String(a.created_at || "")),
  )) {
    const model = r.candidate?.model || r.model || "";
    const cond = r.candidate?.condition || r.condition || "";
    const candId = r.candidate?.id || r.candidateId || r.candidate?.label || r.run_id || r.id;
    const key = model || cond ? `${model}/${cond}/${candId}` : String(candId);
    if (!map.has(key)) map.set(key, r);
  }
  return [...map.values()];
}

export function getMinimalTrace(failure: any): any[] {
  if (Array.isArray(failure?.minimal_stream) && failure.minimal_stream.length > 0) {
    return failure.minimal_stream;
  }
  if (Array.isArray(failure?.shrink_history) && failure.shrink_history.length > 0) {
    const last = failure.shrink_history[failure.shrink_history.length - 1];
    if (Array.isArray(last) && last.length > 0) return last;
  }
  if (Array.isArray(failure?.stream) && failure.stream.length > 0) {
    return failure.stream;
  }
  return [];
}
