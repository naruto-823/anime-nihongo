import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Review from "../src/pages/Review";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Review page", () => {
  it("shows the current vocab card", async () => {
    wrap(<Review />);
    await waitFor(() => expect(screen.getByText("猫")).toBeInTheDocument());
    expect(screen.getByText(/还有 1 项/)).toBeInTheDocument();
  });
});
