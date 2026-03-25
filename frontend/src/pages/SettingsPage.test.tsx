import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { SettingsPage } from "./SettingsPage";

const hookState = vi.hoisted(() => ({
  settings: {
    isLoading: false,
    data: {
      default_analysis_period_days: 14,
      debug_enabled: false,
      sales_tax_rate: 0.036,
      broker_fee_rate: 0.03,
      min_confidence_for_local_structure_demand: 0.75,
      default_user_structure_poll_interval_minutes: 30,
      snapshot_retention_days: 30,
      fallback_policy: "regional_fallback",
      shipping_cost_per_m3: 350,
      default_filters: {},
    },
  },
  updateSettings: {
    isPending: false,
    mutate: vi.fn(),
  },
}));

vi.mock("../hooks/useSettingsData", () => ({
  useSettings: () => hookState.settings,
  useUpdateSettings: () => hookState.updateSettings,
}));

function renderSettingsPage() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  hookState.updateSettings.mutate.mockReset();
});

test("renders persisted debug setting", () => {
  renderSettingsPage();

  expect(screen.getByRole("heading", { name: "Trading Defaults" })).toBeInTheDocument();
  expect(screen.getByLabelText("Debug Mode")).not.toBeChecked();
});

test("submits updated debug setting", async () => {
  const user = userEvent.setup();
  renderSettingsPage();

  await user.click(screen.getByLabelText("Debug Mode"));
  await user.click(screen.getByRole("button", { name: "Save Settings" }));

  expect(hookState.updateSettings.mutate).toHaveBeenCalledWith(
    expect.objectContaining({ debug_enabled: true }),
  );
});
