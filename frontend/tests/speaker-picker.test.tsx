import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SpeakerPicker from "../src/components/SpeakerPicker";
import { SpeakerProvider, useSpeaker } from "../src/lib/speaker-context";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SpeakerProvider>{node}</SpeakerProvider>
    </QueryClientProvider>,
  );
}

function Probe() {
  const { speaker } = useSpeaker();
  return <span data-testid="probe">{speaker}</span>;
}

describe("SpeakerPicker", () => {
  it("renders the list of speakers and updates context on change", async () => {
    wrap(<><SpeakerPicker /><Probe /></>);
    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    // 默认 3 (ずんだもん)
    expect(screen.getByTestId("probe").textContent).toBe("3");
    fireEvent.change(select, { target: { value: "2" } });
    expect(screen.getByTestId("probe").textContent).toBe("2");
  });
});
