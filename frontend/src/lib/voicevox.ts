import { useCallback, useRef, useState } from "react";

import { useSpeaker } from "./speaker-context";

export function useVoicevox() {
  const { speaker } = useSpeaker();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const currentRef = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    const a = currentRef.current;
    if (a) { a.pause(); a.currentTime = 0; }
  }, []);

  const speak = useCallback(
    async (text: string, overrideSpeaker?: number) => {
      const sid = overrideSpeaker ?? speaker;
      if (!text.trim()) return;
      setError(null);
      setLoading(true);
      stop();
      try {
        const resp = await fetch("/api/tts/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, speaker: sid }),
        });
        if (!resp.ok) {
          let detail = `${resp.status}`;
          try { const j = await resp.json(); detail = j?.detail ?? detail; } catch { /* ignore */ }
          throw new Error(detail);
        }
        const blob = await resp.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        currentRef.current = audio;
        audio.onended = () => setLoading(false);
        audio.onerror = () => setLoading(false);
        await audio.play();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "TTS 失败";
        setError(msg);
        setLoading(false);
      }
    },
    [speaker, stop],
  );

  return { speak, stop, loading, error };
}
