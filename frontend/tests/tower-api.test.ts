import { describe, expect, it } from "vitest";

import { getTower } from "../src/lib/api";

describe("tower api", () => {
  it("getTower returns levels", async () => {
    const m = await getTower();
    expect(m.levels[0].level).toBe("N5");
  });
});
