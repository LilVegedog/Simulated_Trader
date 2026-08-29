import { describe, expect, it } from "vitest";
import { fmtMoney, fmtPercent, fmtQty, fmtSignedMoney, pnlColor } from "@/lib/format";

describe("formatting", () => {
  it("formats money with two decimals", () => {
    expect(fmtMoney(10000)).toBe("$10,000.00");
  });

  it("signs gains and losses", () => {
    expect(fmtSignedMoney(21.6)).toBe("+$21.60");
    expect(fmtSignedMoney(-6.55)).toBe("-$6.55");
    expect(fmtPercent(-2.494)).toBe("-2.49%");
    expect(fmtPercent(1.9)).toBe("+1.90%");
  });

  it("keeps fractional quantities readable", () => {
    expect(fmtQty(6)).toBe("6");
    expect(fmtQty(0.75)).toBe("0.75");
  });

  it("colours by sign", () => {
    expect(pnlColor(1)).toBe("text-up");
    expect(pnlColor(-1)).toBe("text-down");
    expect(pnlColor(0)).toBe("text-ink-dim");
  });
});
