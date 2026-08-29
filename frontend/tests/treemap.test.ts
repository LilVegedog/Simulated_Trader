import { describe, expect, it } from "vitest";
import { squarify } from "@/lib/treemap";

describe("squarify", () => {
  it("fills the box with one tile per positive value", () => {
    const tiles = squarify(
      [
        { key: "A", value: 60 },
        { key: "B", value: 30 },
        { key: "C", value: 10 },
      ],
      200,
      100,
    );
    expect(tiles.map((t) => t.key)).toEqual(["A", "B", "C"]);
    const area = tiles.reduce((sum, t) => sum + t.width * t.height, 0);
    expect(area).toBeCloseTo(200 * 100, 4);
  });

  it("returns nothing without positive values", () => {
    expect(squarify([{ key: "A", value: 0 }], 200, 100)).toEqual([]);
  });
});
