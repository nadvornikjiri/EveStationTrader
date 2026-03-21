import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { SyncPage } from "./SyncPage";

vi.mock("../hooks/useSyncData", () => ({
  useSyncStatus: () => ({
    data: [
      {
        key: "worker",
        label: "Worker Health",
        status: "healthy",
        last_successful_sync: "2026-03-20T09:00:00Z",
        next_scheduled_sync: "2026-03-20T09:10:00Z",
        recent_error_count: 0,
      },
    ],
  }),
  useSyncJobs: () => ({
    data: [
      {
        id: 1,
        started_at: "2026-03-20T09:00:00Z",
        finished_at: "2026-03-20T09:00:30Z",
        job_type: "foundation_seed_sync",
        status: "success",
        duration_ms: 30000,
        records_processed: 18,
        target_type: "manual",
        target_id: null,
        message: "Seeded foundation data.",
        error_details: null,
      },
    ],
  }),
  useFallbackDiagnostics: () => ({
    data: [
      {
        structure_name: "Perimeter Market Keepstar",
        structure_id: 1,
        demand_source: "local_structure",
        confidence_score: 0.88,
        coverage_pct: 0.82,
      },
    ],
  }),
  useRunSyncJob: () => ({
    isPending: false,
    data: null,
    mutate: vi.fn(),
  }),
}));

test("renders sync dashboard data", () => {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.getByText("Sync Dashboard")).toBeInTheDocument();
  expect(screen.getByText("Worker Health")).toBeInTheDocument();
  expect(screen.getByText("Job History")).toBeInTheDocument();
  expect(screen.getByText("Demand Fallback Diagnostics")).toBeInTheDocument();
});
