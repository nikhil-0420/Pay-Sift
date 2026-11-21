export type EvidenceLabel =
  "SUPPORTED" | "PARTIAL" | "NOT_FOUND" | "CONFLICT" | "NOT_JUDGED";

export interface GroundingSource {
  id: string;
  url: string;
  title: string;
  domain: string;
  snippet: string;
  rank?: number;
  query?: string;
  retrieved_at: string;
}

export interface RuleGrounding {
  label: EvidenceLabel;
  convention: boolean;
  human_reviewed: boolean;
  sources: GroundingSource[];
  quote: string;
  reason: string;
  judge?: { model: string; temperature: number };
}

export interface GroundingData {
  generated_at: string;
  spec_sha: string;
  provider: string;
  rules: Record<string, RuleGrounding>;
}

export const WHY_BUG_ENDPOINT = `${(import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "")}/evidence/search`;

const labels = new Set<EvidenceLabel>([
  "SUPPORTED",
  "PARTIAL",
  "NOT_FOUND",
  "CONFLICT",
  "NOT_JUDGED",
]);

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function normalizeGrounding(raw: unknown): GroundingData | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  const incoming =
    value.rules && typeof value.rules === "object"
      ? (value.rules as Record<string, unknown>)
      : {};
  const rules: Record<string, RuleGrounding> = {};
  for (const [id, rawRule] of Object.entries(incoming)) {
    if (!/^R\d+$/.test(id) || !rawRule || typeof rawRule !== "object") continue;
    const rule = rawRule as Record<string, unknown>;
    const label =
      typeof rule.label === "string" && labels.has(rule.label as EvidenceLabel)
        ? (rule.label as EvidenceLabel)
        : "NOT_JUDGED";
    const sources = Array.isArray(rule.sources)
      ? rule.sources.flatMap((item): GroundingSource[] => {
          if (!item || typeof item !== "object") return [];
          const source = item as Record<string, unknown>;
          if (
            typeof source.url !== "string" ||
            typeof source.title !== "string"
          )
            return [];
          try {
            const url = new URL(source.url);
            if (!["http:", "https:"].includes(url.protocol)) return [];
            return [
              {
                id: String(source.id || url.href),
                url: url.href,
                title: source.title,
                domain: String(source.domain || url.hostname),
                snippet: stringValue(source.snippet),
                rank: typeof source.rank === "number" ? source.rank : undefined,
                query: stringValue(source.query) || undefined,
                retrieved_at: stringValue(source.retrieved_at),
              },
            ];
          } catch {
            return [];
          }
        })
      : [];
    const judge =
      rule.judge && typeof rule.judge === "object"
        ? (rule.judge as Record<string, unknown>)
        : undefined;
    rules[id] = {
      label,
      convention: rule.convention === true,
      human_reviewed: rule.human_reviewed === true,
      sources,
      quote: stringValue(rule.quote),
      reason: stringValue(rule.reason),
      judge: judge
        ? {
            model: stringValue(judge.model),
            temperature:
              typeof judge.temperature === "number" ? judge.temperature : 0,
          }
        : undefined,
    };
  }
  return {
    generated_at: stringValue(value.generated_at),
    spec_sha: stringValue(value.spec_sha),
    provider: stringValue(value.provider),
    rules,
  };
}

export async function readGrounding(): Promise<GroundingData | null> {
  if (
    import.meta.env.DEV &&
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("fixture") === "evidence"
  ) {
    return normalizeGrounding({
      generated_at: "2026-11-21T00:00:00Z",
      spec_sha: "sample-spec-sha",
      provider: "fixture",
      rules: {
        R3: {
          label: "PARTIAL",
          convention: false,
          human_reviewed: false,
          quote: "Sample fixture only.",
          reason: "Illustrative fixture content.",
          sources: [
            {
              id: "sample-source-1",
              url: "https://example.com/sample-documentation",
              title: "Sample evidence fixture — not a real source",
              domain: "example.com",
              snippet: "Replace with retrieved evidence.",
              retrieved_at: "2026-11-21T00:00:00Z",
            },
          ],
        },
      },
    });
  }
  try {
    let response = await fetch("/data/grounding.json").catch(() => null);
    if (!response || !response.ok) {
      response = await fetch("/data/runs/grounding.json").catch(() => null);
    }
    if (!response || !response.ok) return null;
    return normalizeGrounding(await response.json());
  } catch {
    return null;
  }
}

export function joinEvidenceToFailures<T extends { rule?: string }>(
  failures: T[],
  grounding: GroundingData | null,
): (T & { evidence?: RuleGrounding })[] {
  if (!Array.isArray(failures)) return [];
  return failures.map((f) => ({
    ...f,
    evidence:
      f.rule && grounding?.rules?.[f.rule] ? grounding.rules[f.rule] : undefined,
  }));
}

export function citedRuleCount(data: GroundingData | null | undefined): number {
  return data
    ? Object.values(data.rules).filter(
        (rule) => !rule.convention && rule.sources.length > 0,
      ).length
    : 0;
}
