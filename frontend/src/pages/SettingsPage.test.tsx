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
      source_region_ids: [] as number[],
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
  sourceRegionOptions: {
    data: [
      { region_id: 10000043, name: "Domain" },
      { region_id: 10000030, name: "Heimatar" },
      { region_id: 10000042, name: "Metropolis" },
      { region_id: 10000032, name: "Sinq Laison" },
      { region_id: 10000002, name: "The Forge" },
      { region_id: 10000003, name: "Vale of the Silent" },
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
  useSourceRegionOptions: () => hookState.sourceRegionOptions,
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
  hookState.settings.isLoading = false;
  hookState.settings.data = {
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
    source_region_ids: [],
    default_filters: {},
  };
  hookState.updateSettings.mutate.mockReset();
});

test("renders persisted debug setting", () => {
  renderSettingsPage();

  expect(screen.getByRole("heading", { name: "Trading Defaults" })).toBeInTheDocument();
  expect(screen.getByLabelText("Debug Mode")).not.toBeChecked();
  expect(screen.getByRole("heading", { name: "Source Regions" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Toggle Target Market Hubs" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Toggle Source Regions" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("Jita IV - Moon 4 - Caldari Navy Assembly Plant")).toBeInTheDocument();
  expect(screen.getByText("Select source regions")).toBeInTheDocument();
  expect(screen.queryByLabelText("The Forge")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Vale of the Silent")).not.toBeInTheDocument();
});

test("submits updated debug setting", async () => {
  const user = userEvent.setup();
  renderSettingsPage();

  await user.click(screen.getByLabelText("Debug Mode"));
  await user.click(screen.getByLabelText("Trade Groups per Page"));
  await user.keyboard("{Control>}a{/Control}30");
  await user.click(screen.getByRole("button", { name: "Toggle Target Market Hubs" }));
  expect(screen.getByText("Type at least 4 characters to search.")).toBeInTheDocument();
  await user.click(screen.getByLabelText("Target Market Hubs search"));
  await user.keyboard("Ama");
  expect(screen.getByText("Type at least 4 characters to search.")).toBeInTheDocument();
  await user.keyboard("r");
  await user.click(screen.getByRole("option", { name: /Amarr VIII \(Oris\) - Emperor Family Academy/ }));
  await user.click(screen.getByRole("button", { name: "Toggle Source Regions" }));
  expect(screen.getAllByText("Type at least 4 characters to search.")).not.toHaveLength(0);
  await user.click(screen.getByLabelText("Source Regions search"));
  await user.keyboard("Vale");
  expect(screen.getByRole("option", { name: /Vale of the Silent/ })).toHaveAttribute("aria-selected", "false");
  await user.clear(screen.getByLabelText("Source Regions search"));
  await user.keyboard("Doma");
  await user.click(screen.getByRole("option", { name: /Domain/ }));
  await user.click(screen.getByRole("button", { name: "Save Settings" }));

  expect(hookState.updateSettings.mutate).toHaveBeenCalledWith(
    expect.objectContaining({
      debug_enabled: true,
      trade_groups_page_size: 30,
      target_market_location_ids: [60003760, 60008494],
      source_region_ids: [10000043],
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

test("expands hidden chips without opening the dropdown", async () => {
  const user = userEvent.setup();
  hookState.settings.data = {
    ...hookState.settings.data,
    source_region_ids: [10000043, 10000030, 10000042, 10000032],
  };
  renderSettingsPage();

  await user.click(screen.getByRole("button", { name: /Show 1 more selected items/ }));

  expect(screen.getByText("Sinq Laison")).toBeInTheDocument();
  expect(screen.queryByText("Type at least 4 characters to search.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Toggle Source Regions" })).toHaveAttribute("aria-expanded", "false");
});
