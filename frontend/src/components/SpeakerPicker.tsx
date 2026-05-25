import { useQuery } from "@tanstack/react-query";

import { getSpeakers } from "../lib/api";
import { useSpeaker } from "../lib/speaker-context";

export default function SpeakerPicker() {
  const { speaker, setSpeaker } = useSpeaker();
  const { data, isLoading, error } = useQuery({
    queryKey: ["voicevox-speakers"],
    queryFn: getSpeakers,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });

  if (isLoading) {
    return <span className="text-xs text-ink-400">音色…</span>;
  }
  if (error || !data) {
    return (
      <span className="text-xs text-ink-400" title="VOICEVOX 引擎未启动">
        🔇 TTS 离线
      </span>
    );
  }

  return (
    <select
      value={speaker}
      onChange={(e) => setSpeaker(Number(e.target.value))}
      className="input py-1 text-xs max-w-[20ch]"
      title="VOICEVOX 音色"
    >
      {data.map((c) =>
        c.styles.map((st) => (
          <option key={st.id} value={st.id}>
            {c.name} · {st.name}
          </option>
        )),
      )}
    </select>
  );
}
