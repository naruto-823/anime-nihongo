import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Grammar from "../src/pages/Grammar";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("词库 page", () => {
  it("defaults to the vocab tab and lists words", async () => {
    wrap(<Grammar />);
    await waitFor(() => expect(screen.getByText("元気")).toBeInTheDocument());
    expect(screen.getByText("精神；健康")).toBeInTheDocument();
  });

  it("switches to the grammar tab and renders the N2 group", async () => {
    wrap(<Grammar />);
    fireEvent.click(screen.getByText("📚 语法"));
    await waitFor(() => expect(screen.getByText("N2")).toBeInTheDocument());
    expect(screen.getByText("〜にあたって")).toBeInTheDocument();
  });

  it("opens the detail drawer with the conjugation table on row click", async () => {
    wrap(<Grammar />);
    await waitFor(() => expect(screen.getByText("元気")).toBeInTheDocument());
    fireEvent.click(screen.getByText("元気"));
    await waitFor(() => expect(screen.getByText("活用表")).toBeInTheDocument());
    expect(screen.getByText("食べて")).toBeInTheDocument();
  });
});
