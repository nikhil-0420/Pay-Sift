import { describe, it, expect } from "vitest";
import {
  alignSubsequence,
  formatMoney,
  invariantKeys,
  isFinancial,
  latestPerCandidate,
  moneyDelta,
  normalizeRun,
} from "../src/lib/helpers";
describe("ledger helpers", () => {
  it("formats Indian grouping and paise", () => {
    expect(formatMoney(123456789)).toBe("₹12,34,567.89");
    expect(formatMoney(100000)).toBe("₹1,000");
  });
  it("sorts dynamic invariants and splits I5 from financial", () => {
    expect(
      invariantKeys({ I5_interface: 1, I1_signature: 1, I2_x: 1 }),
    ).toEqual(["I1_signature", "I2_x", "I5_interface"]);
    expect(isFinancial("I4_any")).toBe(true);
    expect(isFinancial("I5_any")).toBe(false);
  });
  it("aligns duplicate events left-to-right", () => {
    const a = [
      { raw_body_b64: "x", signature: "s" },
      { raw_body_b64: "x", signature: "s" },
      { raw_body_b64: "y", signature: "s" },
    ];
    expect(alignSubsequence(a, [a[1], a[2]])).toEqual({
      survivors: [0, 2],
      removed: [1],
    });
  });
  it("tolerates absent fields", () => {
    expect(normalizeRun(null).failures).toEqual([]);
  });
  it("does not fabricate ledger delta", () => {
    expect(moneyDelta({ expected: {}, observed: {} })).toBeNull();
  });
  it("selects most recent candidate", () => {
    expect(
      latestPerCandidate([
        { candidate: { id: "m" }, created_at: "2020" },
        { candidate: { id: "m" }, created_at: "2022" },
      ])[0].created_at,
    ).toBe("2022");
  });
});
