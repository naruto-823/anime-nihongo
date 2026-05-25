import { createContext, useCallback, useContext, useState } from "react";

type Ctx = { speaker: number; setSpeaker: (s: number) => void };

const KEY = "anime-nihongo:speaker";
const DEFAULT_SPEAKER = 3; // ずんだもん

const SpeakerContext = createContext<Ctx>({
  speaker: DEFAULT_SPEAKER,
  setSpeaker: () => {},
});

export function SpeakerProvider({ children }: { children: React.ReactNode }) {
  const [speaker, setSpeakerState] = useState<number>(() => {
    if (typeof window === "undefined") return DEFAULT_SPEAKER;
    const stored = window.localStorage.getItem(KEY);
    const n = stored ? Number(stored) : NaN;
    return Number.isFinite(n) ? n : DEFAULT_SPEAKER;
  });

  const setSpeaker = useCallback((s: number) => {
    setSpeakerState(s);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(KEY, String(s));
    }
  }, []);

  return (
    <SpeakerContext.Provider value={{ speaker, setSpeaker }}>
      {children}
    </SpeakerContext.Provider>
  );
}

export function useSpeaker() {
  return useContext(SpeakerContext);
}
