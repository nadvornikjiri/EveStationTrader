import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { SyncPage } from "./SyncPage";

const hookState = vi.hoisted(() => ({
  runJob: {
    isPending: false,
    data: null as null | {
      id: number;
      started_at: string;
      finished_at: string | null;
      job_type: string;
      status: string;
      duration_ms: number | null;
      records_processed: number;
      target_type: string | null;
      target_id: string | null;
      progress_phase: string | null;
      progress_current: number | null;
      progress_total: number | null;
      progress_unit: string | null;
      message: string | null;
      error_details: string | null;
    },
    mutate: vi.fn(),
  },
}));

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
        active_message: null,
        progress_phase: null,
        progress_current: null,
        progress_total: null,
        progress_unit: null,
      },
      {
        key: "esi_market_orders_sync",
        label: "ESI market orders sync",
        status: "running",
        last_successful_sync: null,
        next_scheduled_sync: null,
        recent_error_count: 0,
        active_message: "Processed 60 / 100 downloaded ESI market orders.",
        progress_phase: "Processing downloaded ESI market orders",
        progress_current: 60,
        progress_total: 100,
        progress_unit: "downloaded records",
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
        progress_phase: null,
        progress_current: null,
        progress_total: null,
        progress_unit: null,
        message: "Seeded foundation data.",
        error_details: null,
      },
      {
        id: 2,
        started_at: "2026-03-23T12:00:00Z",
        finished_at: null,
        job_type: "esi_market_orders_sync",
        status: "running",
        duration_ms: null,
        records_processed: 60,
        target_type: "regions",
        target_id: "1",
        progress_phase: "Processing downloaded ESI market orders",
        progress_current: 60,
        progress_total: 100,
        progress_unit: "downloaded records",
        message: "Processed 60 / 100 downloaded ESI market orders.",
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
  useRunSyncJob: () => hookState.runJob,
  useCancelSyncJob: () => ({
    isPending: false,
    data: null,
    mutate: vi.fn(),
  }),
}));

function renderSyncPage() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  hookState.runJob.isPending = false;
  hookState.runJob.data = null;
  hookState.runJob.mutate.mockReset();
});

test("renders sync dashboard data", () => {
  renderSyncPage();

  expect(screen.getByText("Sync Dashboard")).toBeInTheDocument();
  expect(screen.getByText("Worker Health")).toBeInTheDocument();
  expect(screen.getByText("Job History")).toBeInTheDocument();
  expect(screen.getByText("Demand Fallback Diagnostics")).toBeInTheDocument();
});

test("surfaces immediate run-job failures from sync buttons", () => {
  hookState.runJob.data = {
    id: 2,
    started_at: "2026-03-23T12:00:00Z",
    finished_at: "2026-03-23T12:00:01Z",
    job_type: "foundation_import_sync",
    status: "failed",
    duration_ms: 1000,
    records_processed: 0,
    target_type: "manual",
    target_id: null,
    progress_phase: null,
    progress_current: null,
    progress_total: null,
    progress_unit: null,
    message: "Failed foundation_import_sync.",
    error_details: "Timed out downloading CCP static data.",
  };

  renderSyncPage();

  expect(screen.getByRole("alert")).toHaveTextContent("Sync job failed:");
  expect(screen.getByRole("alert")).toHaveTextContent("Timed out downloading CCP static data.");
  expect(screen.getAllByText("Timed out downloading CCP static data.")).toHaveLength(2);
});

test("shows running progress for active sync jobs", () => {
  renderSyncPage();

  expect(screen.getAllByText("Processing downloaded ESI market orders")).not.toHaveLength(0);
  expect(screen.getAllByText("60 / 100 downloaded records")).not.toHaveLength(0);
  expect(screen.getByLabelText("ESI market orders sync progress")).toBeInTheDocument();
  expect(screen.getByLabelText("esi_market_orders_sync progress")).toBeInTheDocument();
});
