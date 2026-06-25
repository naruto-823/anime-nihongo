import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Tower from "../src/pages/Tower";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><Tower /></MemoryRouter>
    </QueryClientProvider>);
}

describe("Tower page", () => {
  it("renders N5 level and a stage node", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText("N5")).toBeInTheDocument());
    expect(screen.getByText(/第 1 关|1关|关 1/)).toBeInTheDocument();
  });
});
