import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrowserRouter } from "react-router-dom";

import Series from "../src/pages/Series";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>
    <BrowserRouter>{node}</BrowserRouter>
  </QueryClientProvider>);
}

describe("Series page", () => {
  it("lists series from mocked API", async () => {
    wrap(<Series />);
    await waitFor(() => expect(screen.getByText("测试番")).toBeInTheDocument());
    expect(screen.getByText("当前")).toBeInTheDocument();
  });
});
