import { describe, expect, it } from "vitest";

import { getChecklist, getProgress, getToday, listSeries } from "../src/lib/api";

describe("api client", () => {
  it("listSeries", async () => {
    const xs = await listSeries();
    expect(xs[0].title).toBe("测试番");
  });
  it("getToday", async () => {
    const t = await getToday();
    expect(t.streak).toBe(5);
    expect(t.due.vocab).toBe(3);
  });
  it("getChecklist groups by level", async () => {
    const c = await getChecklist();
    expect(Object.keys(c)).toContain("N2");
  });
  it("getProgress", async () => {
    const p = await getProgress();
    expect(p.vocab.in_srs).toBe(7);
  });
});
