import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrowserRouter } from "react-router-dom";

import Today from "../src/pages/Today";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>{node}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("Today page", () => {
  it("renders streak, due counts and current episode", async () => {
    wrap(<Today />);
    await waitFor(() => expect(screen.getByText(/连续/)).toBeInTheDocument());
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/词汇/)).toBeInTheDocument();
    // "3" appears in both the hero summary and the SRS card breakdown; use getAllByText
    expect(screen.getAllByText(/3/).length).toBeGreaterThan(0);
    expect(screen.getByText(/第 1 集/)).toBeInTheDocument();
  });
});
