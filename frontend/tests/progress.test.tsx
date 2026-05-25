import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Progress from "../src/pages/Progress";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Progress page", () => {
  it("renders the three stat cards", async () => {
    wrap(<Progress />);
    await waitFor(() => expect(screen.getByText("5 天")).toBeInTheDocument());
    expect(screen.getByText(/7 \/ 10/)).toBeInTheDocument();
    expect(screen.getByText(/2 \/ 264/)).toBeInTheDocument();
  });
});
