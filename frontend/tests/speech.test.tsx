import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSTT, useTTS } from "../src/lib/speech";

describe("speech hooks", () => {
  it("useSTT exposes supported/listening flags and control fns", () => {
    const { result } = renderHook(() => useSTT());
    // jsdom 没有 webkitSpeechRecognition，supported 应为 false 且不抛
    expect(typeof result.current.supported).toBe("boolean");
    expect(typeof result.current.listening).toBe("boolean");
    expect(typeof result.current.start).toBe("function");
    expect(typeof result.current.stop).toBe("function");
  });

  it("useTTS exposes supported and speak fn; speak with TTS off is a no-op", () => {
    const { result } = renderHook(() => useTTS());
    expect(typeof result.current.supported).toBe("boolean");
    expect(() => result.current.speak("こんにちは")).not.toThrow();
  });
});
