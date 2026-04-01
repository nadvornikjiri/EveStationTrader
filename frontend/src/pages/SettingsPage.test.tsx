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
      trade_groups_page_size: 20,
      debug_enabled: false,
      sales_tax_rate: 0.036,
      broker_fee_rate: 0.03,
      default_user_structure_poll_interval_minutes: 30,
      snapshot_retention_days: 30,
      fallback_policy: "regional_fallback",
      shipping_cost_per_m3: 350,
      target_market_location_ids: [60003760],
      default_filters: {},
    },
  },
  targetOptions: {
    data: [
      {
        location_id: 60003760,
        name: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        location_type: "npc_station",
        region_name: "The Forge",
        system_name: "Jita",
      },
      {
        location_id: 60008494,
        name: "Amarr VIII (Oris) - Emperor Family Academy",
        location_type: "npc_station",
        region_name: "Domain",
        system_name: "Amarr",
      },
    ],
  },
  updateSettings: {
    isPending: false,
    mutate: vi.fn(),
  },
}));

vi.mock("../hooks/useTradeData", () => ({
  useTargetOptions: () => hookState.targetOptions,
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
  await user.click(screen.getByLabelText("Trade Groups per Page"));
  await user.keyboard("{Control>}a{/Control}30");
  await user.click(screen.getByLabelText("Amarr VIII (Oris) - Emperor Family Academy"));
  await user.click(screen.getByRole("button", { name: "Save Settings" }));

  expect(hookState.updateSettings.mutate).toHaveBeenCalledWith(
    expect.objectContaining({
      debug_enabled: true,
      trade_groups_page_size: 30,
      target_market_location_ids: [60003760, 60008494],
    }),
    expect.objectContaining({ onSuccess: expect.any(Function) }),
  );
});

test("save button stays enabled when settings data is present", () => {
  hookState.settings.isLoading = true;
  renderSettingsPage();

  expect(screen.getByRole("button", { name: "Save Settings" })).toBeEnabled();

  hookState.settings.isLoading = false;
});
