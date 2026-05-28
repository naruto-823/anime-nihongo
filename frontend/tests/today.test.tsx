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
  it("renders character header, streak chip and scene timeline", async () => {
    wrap(<Today />);
    await waitFor(() => expect(screen.getByText("测试番")).toBeInTheDocument());
    expect(screen.getByText(/5 天/)).toBeInTheDocument();
    expect(screen.getByText(/4 到期/)).toBeInTheDocument();
    expect(screen.getByText(/开场/)).toBeInTheDocument();
    expect(screen.getByText(/继续读这一场/)).toBeInTheDocument();
  });
});
