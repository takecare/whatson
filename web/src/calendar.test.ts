import { describe, expect, it } from "vitest";
import { monthGrid } from "./calendar";

describe("monthGrid", () => {
  it("lays a month out Monday first", () => {
    const oct = monthGrid("2026-10"); // 1 October 2026 is a Thursday
    expect(oct.slice(0, 4)).toEqual([null, null, null, "2026-10-01"]);
    expect(oct.filter(Boolean)).toHaveLength(31);
    expect(oct[oct.length - 1]).toBe("2026-10-31");
    expect(monthGrid("2026-02").filter(Boolean)).toHaveLength(28);
    expect(monthGrid("2026-06")[0]).toBe("2026-06-01"); // a Monday: no padding
  });
});
