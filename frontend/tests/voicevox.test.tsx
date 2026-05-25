import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useVoicevox } from "../src/lib/voicevox";

describe("useVoicevox", () => {
  it("initializes with no loading and no error", () => {
    const { result } = renderHook(() => useVoicevox());
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.speak).toBe("function");
    expect(typeof result.current.stop).toBe("function");
  });
});
