import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppRoutes } from "./AppRoutes";

vi.mock("../hooks/useTradeData", () => ({
  useTargets: () => ({ data: [] }),
  useSourceSummaries: () => ({ data: [], refetch: vi.fn() }),
  useOpportunityItems: () => ({ data: [] }),
}));

test("renders settings route", async () => {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/settings"]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText("Trading Defaults")).toBeInTheDocument();
});
