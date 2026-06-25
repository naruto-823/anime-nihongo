import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Quiz from "../src/pages/Quiz";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/quiz?level=N5&zone=0&stage=0"]}>
        <Quiz />
      </MemoryRouter>
    </QueryClientProvider>);
}

describe("Quiz page", () => {
  it("shows a question then result after answering", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText("高校（こうこう）")).toBeInTheDocument());
    fireEvent.click(screen.getByText("高中"));
    await waitFor(() => expect(screen.getAllByText(/本关结算|结算|XP/).length).toBeGreaterThan(0));
  });
});
