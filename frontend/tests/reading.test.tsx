import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Reading from "../src/pages/Reading";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/episodes/10/reading"]}>
        <Routes>
          <Route path="/episodes/:id/reading" element={<Reading />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Reading page", () => {
  it("renders lines with speaker/translation toggles", async () => {
    wrap();
    await waitFor(() => expect(screen.getByRole("heading", { name: /精读/ })).toBeInTheDocument());
    expect(screen.getByText(/おはよう/)).toBeInTheDocument();
  });
});
