import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Grammar from "../src/pages/Grammar";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Grammar page", () => {
  it("renders the N2 group and points", async () => {
    wrap(<Grammar />);
    await waitFor(() => expect(screen.getByText("N2")).toBeInTheDocument());
    expect(screen.getByText("〜にあたって")).toBeInTheDocument();
  });
});
