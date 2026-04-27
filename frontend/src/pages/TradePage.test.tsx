import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import * as tradeApi from "../api/trade";
import { TradePage } from "./TradePage";

const mockUseSettings = vi.fn();
const mockUseTargets = vi.fn();
const mockUseSourceSummaries = vi.fn();
const mockUseSources = vi.fn();
const mockUseOpportunityItems = vi.fn();
const mockUseOpportunityItemDetail = vi.fn();
const mockUseTargetOpportunityItems = vi.fn();
const mockUseInTransitAssets = vi.fn();
const mockUseUpsertInTransitAsset = vi.fn();
const mockUseDeleteInTransitAsset = vi.fn();

vi.mock("../hooks/useSettingsData", () => ({
  useSettings: () => mockUseSettings(),
}));

vi.mock("../hooks/useTradeData", () => ({
  useTargets: () => mockUseTargets(),
  useSourceSummaries: (targetLocationId: number | null, periodDays: number, filters: unknown, enabled: boolean) =>
    mockUseSourceSummaries(targetLocationId, periodDays, filters, enabled),
  useSources: (targetLocationId: number | null, periodDays: number, enabled: boolean) =>
    mockUseSources(targetLocationId, periodDays, enabled),
  useOpportunityItems: (
    targetLocationId: number | null,
    sourceLocationId: number | null,
    periodDays: number,
    filters: unknown,
    enabled: boolean,
  ) => mockUseOpportunityItems(targetLocationId, sourceLocationId, periodDays, filters, enabled),
  useOpportunityItemDetail: (
    targetLocationId: number | null,
    sourceLocationId: number | null,
    typeId: number | null,
    periodDays: number,
  ) => mockUseOpportunityItemDetail(targetLocationId, sourceLocationId, typeId, periodDays),
  useTargetOpportunityItems: (targetLocationId: number | null, periodDays: number, enabled: boolean) =>
    mockUseTargetOpportunityItems(targetLocationId, periodDays, enabled),
  useInTransitAssets: (targetLocationId: number | null, enabled: boolean) =>
    mockUseInTransitAssets(targetLocationId, enabled),
  useUpsertInTransitAsset: () => mockUseUpsertInTransitAsset(),
  useDeleteInTransitAsset: () => mockUseDeleteInTransitAsset(),
}));

const targets = [
  { location_id: 1, name: "Jita", location_type: "npc_station", region_name: "The Forge", system_name: "Jita" },
  { location_id: 3, name: "Perimeter Keepstar", location_type: "structure", region_name: "The Forge", system_name: "Perimeter" },
];

const summaryRowsByTarget: Record<number, Array<Record<string, number | string>>> = {
  1: [
    {
      source_location_id: 2,
      source_market_name: "Amarr",
      source_security_status: 1,
      purchase_units_total: 5,
      source_units_available_total: 10,
      target_demand_day_total: 12,
      target_supply_units_total: 20,
      target_dos_weighted: 1.5,
      in_transit_units: 0,
      assets_units: 0,
      active_sell_orders_units: 0,
      source_avg_price_weighted: 100,
      target_now_price_weighted: 120,
      target_period_avg_price_weighted: 130,
      target_now_profit_weighted: 12,
      target_period_profit_weighted: 18,
      capital_required_total: 500,
      roi_now_weighted: 0.12,
      roi_period_weighted: 0.18,
      total_item_volume_m3: 5,
      shipping_cost_total: 10,
      demand_source_summary: "Adam4EVE",
      esi_demand_day_total: 0,
    },
    {
      source_location_id: 5,
      source_market_name: "Dodixie",
      source_security_status: 0.9,
      purchase_units_total: 3,
      source_units_available_total: 15,
      target_demand_day_total: 8,
      target_supply_units_total: 10,
      target_dos_weighted: 1.25,
      in_transit_units: 0,
      assets_units: 0,
      active_sell_orders_units: 0,
      source_avg_price_weighted: 90,
      target_now_price_weighted: 120,
      target_period_avg_price_weighted: 125,
      target_now_profit_weighted: 15,
      target_period_profit_weighted: 18,
      capital_required_total: 270,
      roi_now_weighted: 0.2,
      roi_period_weighted: 0.25,
      total_item_volume_m3: 2,
      shipping_cost_total: 8,
      demand_source_summary: "Local",
      esi_demand_day_total: 0,
    },
  ],
  3: [],
};

const itemRowsBySource: Record<number, Array<Record<string, number | string>>> = {
  2: [
    {
      type_id: 34,
      item_name: "Tritanium",
      market_browser_url: "https://evemarketbrowser.com/region/10000002/type/34",
      source_security_status: 1,
      purchase_units: 5,
      source_units_available: 10,
      target_demand_day: 12,
      target_supply_units: 20,
      target_dos: 1.5,
      in_transit_units_item: 0,
      assets_units_item: 0,
      active_sell_orders_units_item: 0,
      source_station_sell_price: 100,
      target_station_sell_price: 120,
      target_period_avg_price: 130,
      target_now_profit: 12,
      target_period_profit: 18,
      capital_required: 500,
      roi_now: 0.12,
      roi_period: 0.18,
      item_volume_m3: 0.01,
      shipping_cost: 10,
      demand_source: "Adam4EVE",
      esi_demand_day: 0,
    },
    {
      type_id: 35,
      item_name: "Pyerite",
      market_browser_url: "https://evemarketbrowser.com/region/10000002/type/35",
      source_security_status: 1,
      purchase_units: 9,
      source_units_available: 15,
      target_demand_day: 16,
      target_supply_units: 40,
      target_dos: 2.5,
      in_transit_units_item: 0,
      assets_units_item: 0,
      active_sell_orders_units_item: 0,
      source_station_sell_price: 90,
      target_station_sell_price: 97,
      target_period_avg_price: 99,
      target_now_profit: 4,
      target_period_profit: 6,
      capital_required: 810,
      roi_now: 0.03,
      roi_period: 0.05,
      item_volume_m3: 0.01,
      shipping_cost: 12,
      demand_source: "Fallback",
      esi_demand_day: 0,
    },
  ],
  5: [
    {
      type_id: 36,
      item_name: "Mexallon",
      market_browser_url: "https://evemarketbrowser.com/region/10000002/type/36",
      source_security_status: 0.9,
      purchase_units: 7,
      source_units_available: 25,
      target_demand_day: 14,
      target_supply_units: 18,
      target_dos: 1.3,
      in_transit_units_item: 0,
      assets_units_item: 0,
      active_sell_orders_units_item: 0,
      source_station_sell_price: 75,
      target_station_sell_price: 120,
      target_period_avg_price: 122,
      target_now_profit: 33,
      target_period_profit: 35,
      capital_required: 525,
      roi_now: 0.44,
      roi_period: 0.46,
      item_volume_m3: 0.01,
      shipping_cost: 7,
      demand_source: "Local",
      esi_demand_day: 0,
    },
  ],
};

const targetItemsByTarget: Record<number, Array<Record<string, number | string>>> = {
  1: [
    { source_location_id: 2, ...itemRowsBySource[2][0] },
    { source_location_id: 2, ...itemRowsBySource[2][1] },
    { source_location_id: 5, ...itemRowsBySource[5][0] },
  ],
  3: [],
};

type TestTradeFilters = {
  itemSearch: string;
  minProfit: string;
  minRoiNowPct: string;
  minDemandDay: string;
  maxDos: string;
  maxItemVolumeM3: string;
  sourceType: string;
  minSecurity: string;
  demandSource: string;
  minEsiDemandDay: string;
};

function parseFilterNumber(value: string, fallback: number) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function securityThreshold(minSecurity: string) {
  switch (minSecurity) {
    case "highsec":
      return 0.5;
    case "lowsec":
      return 0;
    default:
      return -10;
  }
}

function filterTargetItems(targetLocationId: number | null, filters: TestTradeFilters) {
  const rows = targetLocationId === null ? [] : targetItemsByTarget[targetLocationId] ?? [];
  const searchValue = filters.itemSearch.trim().toLowerCase();
  const minProfitValue = parseFilterNumber(filters.minProfit, 0);
  const minRoiNowThreshold = parseFilterNumber(filters.minRoiNowPct, 0) / 100;
  const minDemandDayValue = parseFilterNumber(filters.minDemandDay, 0);
  const maxDosValue = filters.maxDos.trim().length === 0 ? Number.POSITIVE_INFINITY : parseFilterNumber(filters.maxDos, Number.POSITIVE_INFINITY);
  const maxItemVolumeValue =
    filters.maxItemVolumeM3.trim().length === 0
      ? Number.POSITIVE_INFINITY
      : parseFilterNumber(filters.maxItemVolumeM3, Number.POSITIVE_INFINITY);
  const minSecurityValue = securityThreshold(filters.minSecurity);
  return rows.filter((row) => {
    const sourceSummary = (summaryRowsByTarget[targetLocationId ?? 0] ?? []).find(
      (summary) => summary.source_location_id === row.source_location_id,
    );
    const sourceType = sourceSummary?.source_market_name === "Dodixie" ? "structure" : "npc";
    return (
      (searchValue.length === 0 || String(row.item_name).toLowerCase().includes(searchValue)) &&
      Number(row.target_now_profit) > minProfitValue &&
      (minRoiNowThreshold <= 0 || Number(row.roi_now) > minRoiNowThreshold) &&
      Number(row.target_demand_day) >= minDemandDayValue &&
      Number(row.target_dos) <= maxDosValue &&
      Number(row.item_volume_m3) <= maxItemVolumeValue &&
      Number(row.source_security_status) >= minSecurityValue &&
      (filters.demandSource === "all" || row.demand_source === filters.demandSource) &&
      (filters.sourceType === "all" || sourceType === filters.sourceType)
    );
  });
}

const itemDetailsByType = {
  34: {
    type_id: 34,
    item_name: "Tritanium",
    target_market_sell_orders: [{ price: 120, volume: 12, order_value: 1440, cumulative_volume: 12 }],
    source_market_sell_orders: [{ price: 100, volume: 10, order_value: 1000 }],
    source_market_buy_orders: [{ price: 95, volume: 15, order_value: 1425 }],
    metrics: itemRowsBySource[2][0],
  },
  35: {
    type_id: 35,
    item_name: "Pyerite",
    target_market_sell_orders: [{ price: 97, volume: 8, order_value: 776, cumulative_volume: 8 }],
    source_market_sell_orders: [{ price: 90, volume: 11, order_value: 990 }],
    source_market_buy_orders: [{ price: 87, volume: 12, order_value: 1044 }],
    metrics: itemRowsBySource[2][1],
  },
  36: {
    type_id: 36,
    item_name: "Mexallon",
    target_market_sell_orders: [{ price: 120, volume: 5, order_value: 600, cumulative_volume: 5 }],
    source_market_sell_orders: [{ price: 75, volume: 20, order_value: 1500 }],
    source_market_buy_orders: [{ price: 70, volume: 10, order_value: 700 }],
    metrics: itemRowsBySource[5][0],
  },
};

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TradePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.spyOn(tradeApi, "refreshTradeOpportunities").mockResolvedValue({
    last_refresh_at: "2026-03-30T12:00:00Z",
  });
  mockUseSettings.mockReturnValue({
    data: {
      default_analysis_period_days: 14,
      trade_groups_page_size: 20,
      default_filters: {
        min_item_profit: 0,
        roi_now: 0,
        target_demand_day: 1,
      },
    },
  });
  mockUseTargets.mockReturnValue({ data: targets });
  mockUseSources.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === null ? [] : summaryRowsByTarget[targetLocationId]?.map((row) => ({
      location_id: Number(row.source_location_id),
      name: String(row.source_market_name),
      location_type: "npc_station",
      region_name: "The Forge",
      system_name: String(row.source_market_name),
    })) ?? [],
  }));
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null, _: number, filters: TestTradeFilters, enabled: boolean) => ({
    data:
      !enabled || targetLocationId === null
        ? []
        : (summaryRowsByTarget[targetLocationId] ?? []).filter((summary) =>
            filterTargetItems(targetLocationId, filters).some((row) => row.source_location_id === summary.source_location_id),
          ),
    refetch: vi.fn(),
  }));
  mockUseOpportunityItems.mockImplementation(
    (targetLocationId: number | null, sourceLocationId: number | null, __: number, filters: TestTradeFilters, enabled: boolean) => ({
      data:
        !enabled || sourceLocationId === null
          ? []
          : filterTargetItems(targetLocationId, filters).filter((row) => row.source_location_id === sourceLocationId),
      refetch: vi.fn(),
    }),
  );
  mockUseOpportunityItemDetail.mockImplementation((_: number | null, sourceLocationId: number | null, typeId: number | null) => ({
    data: sourceLocationId === null || typeId === null ? undefined : itemDetailsByType[typeId as keyof typeof itemDetailsByType],
    isLoading: false,
    refetch: vi.fn(),
  }));
  mockUseTargetOpportunityItems.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === null ? [] : targetItemsByTarget[targetLocationId] ?? [],
  }));
  mockUseInTransitAssets.mockReturnValue({ data: [], error: null });
  mockUseUpsertInTransitAsset.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
  mockUseDeleteInTransitAsset.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

test("renders grouped opportunities collapsed by source market on first load", () => {
  renderPage();

  expect(screen.getByText("Grouped Opportunities")).toBeInTheDocument();
  expect(screen.queryByText(/Grouped source rows show purchase-unit-weighted price averages\./)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Analysis Period")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Min ROI")).not.toBeInTheDocument();
  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Amarr")).toBeInTheDocument();
  expect(within(groupedTable).getByText("Dodixie")).toBeInTheDocument();
  expect(within(groupedTable).queryByText("Tritanium")).not.toBeInTheDocument();
  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(
    1,
    14,
    expect.objectContaining({ minProfit: "0", minRoiNowPct: "0", minDemandDay: "1" }),
    true,
  );
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(1, null, null, 14);
});

test("applies semantic metric colors to grouped and expanded trade cells", async () => {
  const user = userEvent.setup();
  renderPage();

  const groupedRow = screen.getByText("Amarr").closest("tr");
  expect(groupedRow).not.toBeNull();
  const groupedCells = groupedRow?.querySelectorAll("td") ?? [];
  expect(groupedCells[12]).toHaveClass("metric-cell-source-price");
  expect(groupedCells[17]).toHaveClass("metric-cell-positive");
  expect(groupedCells[18]).toHaveClass("metric-cell-positive");
  expect(groupedCells[19]).toHaveClass("metric-cell-capital");
  expect(groupedCells[20]).toHaveClass("metric-cell-positive");
  expect(groupedCells[21]).toHaveClass("metric-cell-positive");

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));

  const expandedRow = screen.getAllByText("Tritanium")[0].closest("tr");
  expect(expandedRow).not.toBeNull();
  const expandedCells = expandedRow?.querySelectorAll("td") ?? [];
  expect(expandedCells[12]).toHaveClass("metric-cell-source-price");
  expect(expandedCells[17]).toHaveClass("metric-cell-positive");
  expect(expandedCells[18]).toHaveClass("metric-cell-positive");
  expect(expandedCells[19]).toHaveClass("metric-cell-capital");
  expect(expandedCells[20]).toHaveClass("metric-cell-positive");
  expect(expandedCells[21]).toHaveClass("metric-cell-positive");
});

test("formats item volume cells as whole-number m3 values", async () => {
  const user = userEvent.setup();
  renderPage();

  const groupedRow = screen.getByText("Amarr").closest("tr");
  expect(groupedRow).toHaveTextContent("5 m3");

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));

  const expandedRow = screen.getAllByText("Tritanium")[0].closest("tr");
  expect(expandedRow).toHaveTextContent("0 m3");
});

test("shows source summary query errors instead of the generic empty-state message", () => {
  mockUseSourceSummaries.mockReturnValue({
    data: [],
    error: new Error("API request failed: 500"),
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  });

  renderPage();

  expect(screen.getByText("Load failed")).toBeInTheDocument();
  expect(screen.getByText("Grouped opportunities failed to load: API request failed: 500")).toBeInTheDocument();
  expect(screen.queryByText("No computed source markets available for this target yet.")).not.toBeInTheDocument();
});

test("paginates grouped source markets using the configured settings page size", async () => {
  const user = userEvent.setup();
  const pagedSummaryRows = Array.from({ length: 25 }, (_, index) => ({
    ...summaryRowsByTarget[1][0],
    source_location_id: 100 + index,
    source_market_name: `Source ${String(index + 1).padStart(2, "0")}`,
    target_now_profit_weighted: 1_000 - index,
    esi_demand_day_total: 0,
  }));
  mockUseSourceSummaries.mockImplementation(() => ({
    data: pagedSummaryRows,
    refetch: vi.fn(),
  }));
  renderPage();

  expect(screen.getByText("Showing groups 1-20 of 25")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Expand Source 01" })).toBeInTheDocument();
  expect(screen.queryByText("Source 25")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Next" }));

  expect(screen.getByText("Showing groups 21-25 of 25")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Expand Source 25" })).toBeInTheDocument();
  expect(screen.queryByText("Source 01")).not.toBeInTheDocument();
});

test("expands a source row to show inline item opportunities for that location", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));

  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(groupedTable).getByText("Pyerite")).toBeInTheDocument();
});

test("renders expanded source items in batches so large groups stay responsive", async () => {
  const user = userEvent.setup();
  const largeSourceRows = Array.from({ length: 205 }, (_, index) => ({
    ...itemRowsBySource[2][0],
    type_id: 1000 + index,
    item_name: `Large Item ${index + 1}`,
    target_now_profit: 400 - index,
    roi_now: 0.3,
  }));
  mockUseOpportunityItems.mockImplementation((_targetLocationId, sourceLocationId) => ({
    data: sourceLocationId === 2 ? largeSourceRows : sourceLocationId === 5 ? itemRowsBySource[5] : [],
    refetch: vi.fn(),
  }));

  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));

  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Large Item 1")).toBeInTheDocument();
  expect(within(groupedTable).queryByText("Large Item 205")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Show more item opportunities (200 of 205 shown)" }));

  expect(within(groupedTable).getByText("Large Item 205")).toBeInTheDocument();
});

test("loads item detail when an expanded inline item is selected", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.click(screen.getByText("Pyerite"));

  const detailPanel = screen.getByText("Execution Context").closest("section");
  expect(detailPanel).not.toBeNull();
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(1, 2, 35, 14);
  expect(within(detailPanel as HTMLElement).getByText("Pyerite")).toBeInTheDocument();
  expect(within(detailPanel as HTMLElement).getByText("Fallback")).toBeInTheDocument();
});

test("subtracts same-target in-transit quantity only when adding a new shopping-list item", async () => {
  const user = userEvent.setup();
  mockUseInTransitAssets.mockReturnValue({
    data: [
      {
        id: 1,
        source_location_id: 2,
        source_market_name: "Amarr",
        target_location_id: 1,
        target_market_name: "Jita",
        type_id: 34,
        item_name: "Tritanium",
        quantity: 4,
        note: "Courier load",
        created_at: "2026-03-30T12:00:00Z",
        updated_at: "2026-03-30T12:00:00Z",
      },
    ],
    error: null,
  });
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.click(screen.getByLabelText("Add Tritanium to shopping list"));

  expect(screen.getByDisplayValue("8")).toBeInTheDocument();
});

test("shopping list shows quantity-scaled target profits and total profit summaries", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.click(screen.getByLabelText("Add Tritanium to shopping list"));

  expect(screen.getByText("Total Price:")).toBeInTheDocument();
  expect(screen.getByText("Total Now Profit:")).toBeInTheDocument();
  expect(screen.getByText("Total Period Profit:")).toBeInTheDocument();
  expect(screen.getAllByText("1.20K")).toHaveLength(2);
  expect(screen.getAllByText("144")).toHaveLength(2);
  expect(screen.getAllByText("216")).toHaveLength(2);

  const quantityInput = screen.getByDisplayValue("12");
  fireEvent.change(quantityInput, { target: { value: "3" } });

  expect(screen.getByDisplayValue("3")).toBeInTheDocument();

  expect(screen.getAllByText("300")).toHaveLength(2);
  expect(screen.getAllByText("36")).toHaveLength(2);
  expect(screen.getAllByText("54")).toHaveLength(2);
});

test("opening one bottom overlay minimizes the other and keeps tabs aligned", async () => {
  const user = userEvent.setup();
  mockUseInTransitAssets.mockReturnValue({
    data: [
      {
        id: 1,
        source_location_id: 2,
        source_market_name: "Amarr",
        target_location_id: 1,
        target_market_name: "Jita",
        type_id: 34,
        item_name: "Tritanium",
        quantity: 4,
        note: "Courier load",
        created_at: "2026-03-30T12:00:00Z",
        updated_at: "2026-03-30T12:00:00Z",
      },
    ],
    error: null,
  });
  renderPage();

  const openInTransitTab = () => screen.getAllByRole("button", { name: /In Transit/ }).at(-1) as HTMLElement;
  const openShoppingListTab = () => screen.getByRole("button", { name: /Shopping List/ });

  await user.click(openInTransitTab());
  expect(screen.getByText("Target: Jita")).toBeInTheDocument();
  expect(openInTransitTab()).toHaveAttribute("aria-pressed", "true");

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.click(screen.getByLabelText("Add Tritanium to shopping list"));

  expect(screen.queryByText("Target: Jita")).not.toBeInTheDocument();
  expect(screen.getByText(/Shopping List —/)).toBeInTheDocument();
  expect(openInTransitTab()).toBeInTheDocument();
  expect(openInTransitTab()).toHaveAttribute("aria-pressed", "false");
  expect(openShoppingListTab()).toHaveAttribute("aria-pressed", "true");

  await user.click(openInTransitTab());

  expect(screen.getByText("Target: Jita")).toBeInTheDocument();
  expect(screen.queryByText(/Shopping List —/)).not.toBeInTheDocument();
  expect(openShoppingListTab()).toHaveAttribute("aria-pressed", "false");
  expect(openInTransitTab()).toHaveAttribute("aria-pressed", "true");
});

test("shows a MarketBrowser context menu for expanded item rows", async () => {
  const user = userEvent.setup();
  const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.pointer([
    {
      target: screen.getAllByText("Tritanium")[0],
      keys: "[MouseRight]",
    },
  ]);

  const menu = screen.getByRole("menu", { name: "Tritanium actions" });
  expect(within(menu).getByRole("menuitem", { name: "Open MarketBrowser" })).toBeInTheDocument();

  await user.click(within(menu).getByRole("menuitem", { name: "Open MarketBrowser" }));

  expect(openSpy).toHaveBeenCalledWith(
    "https://evemarketbrowser.com/region/10000002/type/34",
    "_blank",
    "noopener,noreferrer",
  );
});

test("sorts grouped source rows and expanded item rows by shared table columns", async () => {
  const user = userEvent.setup();
  renderPage();

  const groupedTable = screen.getByRole("table");
  let rows = within(groupedTable).getAllByRole("row");
  expect(within(rows[1]).getByText("Dodixie")).toBeInTheDocument();
  expect(within(rows[2]).getByText("Amarr")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Sort by Source Market / Item" }));
  rows = within(groupedTable).getAllByRole("row");
  expect(within(rows[1]).getByText("Amarr")).toBeInTheDocument();
  expect(within(rows[2]).getByText("Dodixie")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  rows = within(groupedTable).getAllByRole("row");
  // rows[2] is the summary note row ("Showing all 2 filtered items...")
  expect(within(rows[3]).getByText("Pyerite")).toBeInTheDocument();
  expect(within(rows[4]).getByText("Tritanium")).toBeInTheDocument();
});

test("changing target requeries grouped summaries using the settings analysis period", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  await user.selectOptions(screen.getByLabelText("Target Market"), "3");
  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(3, 14, expect.any(Object), true);
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(3, null, null, 14);
});

test("renders stable empty and loading states for the grouped table", async () => {
  const user = userEvent.setup();
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === 3 ? [] : targetLocationId === null ? [] : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: vi.fn(),
  }));

  renderPage();

  await user.selectOptions(screen.getByLabelText("Target Market"), "3");
  expect(screen.getByText("No computed source markets available for this target yet.")).toBeInTheDocument();
  expect(screen.getByText("Select an item to inspect its detail.")).toBeInTheDocument();

  mockUseSourceSummaries.mockImplementation(() => ({
    data: undefined,
    isLoading: true,
    isFetching: true,
    refetch: vi.fn(),
  }));
});

test("shows loading copy instead of fake empty state while grouped summaries are still loading", () => {
  mockUseSourceSummaries.mockImplementation(() => ({
    data: undefined,
    isLoading: true,
    isFetching: true,
    refetch: vi.fn(),
  }));
  mockUseOpportunityItems.mockImplementation(() => ({
    data: undefined,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  }));
  mockUseOpportunityItemDetail.mockImplementation(() => ({
    data: undefined,
    isLoading: false,
    refetch: vi.fn(),
  }));

  renderPage();

  expect(screen.getByText("Loading source markets for this target...")).toBeInTheDocument();
  expect(screen.queryByText("No computed source markets available for this target yet.")).not.toBeInTheDocument();
});

test("filters apply to expanded inline item rows", async () => {
  const user = userEvent.setup();
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null, _: number, filters: TestTradeFilters) => ({
    data:
      targetLocationId === 1 && filters.minRoiNowPct === "20"
        ? [summaryRowsByTarget[1][0]]
        : targetLocationId === null
          ? []
          : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: vi.fn(),
  }));
  mockUseOpportunityItems.mockImplementation((_targetLocationId: number | null, sourceLocationId: number | null, __: number, filters: TestTradeFilters) => ({
    data:
      sourceLocationId === 2 && filters.minRoiNowPct === "20"
        ? [{ ...itemRowsBySource[2][0], roi_now: 0.21 }]
        : sourceLocationId === 2
          ? [
              { ...itemRowsBySource[2][0], roi_now: 0.21 },
              { ...itemRowsBySource[2][1], roi_now: 0.2 },
            ]
          : sourceLocationId === 5
            ? [{ ...itemRowsBySource[5][0], roi_now: 0.19 }]
            : [],
    refetch: vi.fn(),
  }));
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(groupedTable).getByText("Pyerite")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("Min ROI Now Pct"));
  await user.type(screen.getByLabelText("Min ROI Now Pct"), "20");
  expect(within(groupedTable).queryByText("Dodixie")).not.toBeInTheDocument();
  expect(within(groupedTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(groupedTable).queryByText("Pyerite")).not.toBeInTheDocument();
  expect(within(groupedTable).queryByText("Mexallon")).not.toBeInTheDocument();
});

test("max item volume filters grouped source rows when no inline items remain", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(groupedTable).getByText("Pyerite")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Max Item Volume M3"), "0.009");

  expect(within(groupedTable).queryByText("Amarr")).not.toBeInTheDocument();
  expect(within(groupedTable).queryByText("Tritanium")).not.toBeInTheDocument();
  expect(within(groupedTable).queryByText("Pyerite")).not.toBeInTheDocument();
  expect(within(groupedTable).getByText("No computed source markets available for this target yet.")).toBeInTheDocument();
});

test("min profit filters against target now profit using a strict greater-than threshold", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "Expand Amarr" }));
  const groupedTable = screen.getByRole("table");
  expect(within(groupedTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(groupedTable).getByText("Pyerite")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Min Profit"), "12");

  expect(within(groupedTable).queryByText("Amarr")).not.toBeInTheDocument();
  expect(within(groupedTable).queryByText("Tritanium")).not.toBeInTheDocument();
  expect(within(groupedTable).queryByText("Pyerite")).not.toBeInTheDocument();
  expect(within(groupedTable).getByText("Dodixie")).toBeInTheDocument();
});

test("numeric filter inputs expose step controls for the configured increments", () => {
  renderPage();

  expect(screen.getByLabelText("Min ROI Now Pct")).toHaveAttribute("step", "5");
  expect(screen.getByLabelText("Min Demand Day")).toHaveAttribute("step", "0.1");
  expect(screen.getByLabelText("Max DOS")).toHaveAttribute("step", "0.1");
  expect(screen.getByLabelText("Max Item Volume M3")).toHaveAttribute("step", "0.01");
});

test("uses the settings analysis period for data queries and refreshes", async () => {
  const user = userEvent.setup();
  mockUseSettings.mockReturnValue({
    data: {
      default_analysis_period_days: 21,
      trade_groups_page_size: 20,
      default_filters: {
        min_item_profit: 0,
        roi_now: 0,
        target_demand_day: 1,
      },
    },
  });

  renderPage();

  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(1, 21, expect.any(Object), true);
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(1, null, null, 21);

  await user.click(screen.getByRole("button", { name: "Rebuild Selected Target" }));

  expect(tradeApi.refreshTradeOpportunities).toHaveBeenCalledWith(1, 21);
});

test("hydrates visible trade filter defaults from settings on first load", () => {
  mockUseSettings.mockReturnValue({
    data: {
      default_analysis_period_days: 14,
      trade_groups_page_size: 20,
      default_filters: {
        min_item_profit: 15000000,
        roi_now: 0.2,
        target_demand_day: 3.5,
      },
    },
  });

  renderPage();

  expect(screen.getByLabelText("Min Profit")).toHaveValue(15000000);
  expect(screen.getByLabelText("Min ROI Now Pct")).toHaveValue(20);
  expect(screen.getByLabelText("Min Demand Day")).toHaveValue(3.5);
});

test("renders sortable headers for the grouped opportunity table", () => {
  renderPage();

  for (const label of [
    "Source Market / Item",
    "Sec",
    "Purchase Units",
    "Source Units Avail",
    "Target Demand / Day",
    "Target Supply Units",
    "Target D.O.S",
    "In Transit",
    "Assets",
    "Active Sell Orders",
    "Source Now Price",
    "Target Now Price",
    "Target Period Avg Price",
    "Target Now Profit",
    "Target Period Profit",
    "Capital Required",
    "ROI Now",
    "ROI Period",
    "Item Volume",
    "Shipping Cost",
    "Demand Source",
  ]) {
    expect(screen.getByRole("button", { name: `Sort by ${label}` })).toBeInTheDocument();
  }
});

test("rebuild selected target button triggers a backend rebuild before refetching grouped summaries", async () => {
  const user = userEvent.setup();
  const summaryRefetch = vi.fn().mockResolvedValue(undefined);
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === null ? [] : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: summaryRefetch,
  }));

  renderPage();

  await user.click(screen.getByRole("button", { name: "Rebuild Selected Target" }));

  expect(tradeApi.refreshTradeOpportunities).toHaveBeenCalledWith(1, 14);
  expect(summaryRefetch).toHaveBeenCalled();
});

test("group totals are rebuilt from only the matching filtered records", async () => {
  const user = userEvent.setup();
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null, _: number, filters: TestTradeFilters) => ({
    data:
      targetLocationId === 1 && filters.minProfit === "20"
        ? [
            {
              ...summaryRowsByTarget[1][1],
              source_units_available_total: 231,
              capital_required_total: 525,
            },
          ]
        : targetLocationId === null
          ? []
          : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: vi.fn(),
  }));
  renderPage();

  await user.type(screen.getByLabelText("Min Profit"), "20");

  const groupedTable = screen.getByRole("table");
  const rows = within(groupedTable).getAllByRole("row");
  expect(within(rows[1]).getByText("Dodixie")).toBeInTheDocument();
  expect(within(rows[1]).getByText("231")).toBeInTheDocument();
  expect(within(rows[1]).getByText("525")).toBeInTheDocument();
  expect(within(groupedTable).queryByText("Amarr")).not.toBeInTheDocument();
});
