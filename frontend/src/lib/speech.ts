import { useCallback, useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => any;
    SpeechRecognition?: new () => any;
  }
}

function getSR() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function useSTT(lang = "ja-JP") {
  const [supported] = useState(() => getSR() !== null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const ref = useRef<any>(null);

  const start = useCallback(() => {
    const Cls = getSR();
    if (!Cls || listening) return;
    const rec = new Cls();
    rec.lang = lang;
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e: any) => {
      const t = e.results?.[0]?.[0]?.transcript ?? "";
      setTranscript(t);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    ref.current = rec;
    setTranscript("");
    setListening(true);
    rec.start();
  }, [lang, listening]);

  const stop = useCallback(() => {
    ref.current?.stop?.();
    setListening(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { supported, listening, transcript, start, stop };
}

export function useTTS(lang = "ja-JP") {
  const supported =
    typeof window !== "undefined" && "speechSynthesis" in window;
  const speak = useCallback(
    (text: string) => {
      if (!supported || !text) return;
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    },
    [lang, supported],
  );
  return { supported, speak };
}
