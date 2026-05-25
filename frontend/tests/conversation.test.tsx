import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Conversation from "../src/pages/Conversation";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/episodes/10/conversation"]}>
        <Routes>
          <Route path="/episodes/:id/conversation" element={<Conversation />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Conversation page", () => {
  it("renders header for episode and the typing input", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText(/第 1 集/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText(/说点什么/)).toBeInTheDocument();
  });
});
