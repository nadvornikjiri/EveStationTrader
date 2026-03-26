import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { TradePage } from "./TradePage";

const mockUseTargets = vi.fn();
const mockUseSourceSummaries = vi.fn();
const mockUseOpportunityItems = vi.fn();
const mockUseOpportunityItemDetail = vi.fn();

vi.mock("../hooks/useTradeData", () => ({
  useTargets: () => mockUseTargets(),
  useSourceSummaries: (targetLocationId: number | null, periodDays: number) =>
    mockUseSourceSummaries(targetLocationId, periodDays),
  useOpportunityItems: (targetLocationId: number | null, sourceLocationId: number | null, periodDays: number) =>
    mockUseOpportunityItems(targetLocationId, sourceLocationId, periodDays),
  useOpportunityItemDetail: (
    targetLocationId: number | null,
    sourceLocationId: number | null,
    typeId: number | null,
    periodDays: number,
  ) => mockUseOpportunityItemDetail(targetLocationId, sourceLocationId, typeId, periodDays),
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
      confidence_score_summary: 0.9,
    },
  ],
  3: [
    {
      source_location_id: 4,
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
      confidence_score_summary: 0.95,
    },
  ],
};

const itemRows = [
  {
    type_id: 34,
    item_name: "Tritanium",
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
    confidence_score: 0.9,
  },
  {
    type_id: 35,
    item_name: "Pyerite",
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
    confidence_score: 0.5,
  },
];

const itemDetailsByType = {
  34: {
    type_id: 34,
    item_name: "Tritanium",
    target_market_sell_orders: [{ price: 120, volume: 12, order_value: 1440, cumulative_volume: 12 }],
    source_market_sell_orders: [{ price: 100, volume: 10, order_value: 1000 }],
    source_market_buy_orders: [{ price: 95, volume: 15, order_value: 1425 }],
    metrics: itemRows[0],
  },
  35: {
    type_id: 35,
    item_name: "Pyerite",
    target_market_sell_orders: [{ price: 97, volume: 8, order_value: 776, cumulative_volume: 8 }],
    source_market_sell_orders: [{ price: 90, volume: 11, order_value: 990 }],
    source_market_buy_orders: [{ price: 87, volume: 12, order_value: 1044 }],
    metrics: itemRows[1],
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
  mockUseTargets.mockReturnValue({ data: targets });
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === null ? [] : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: vi.fn(),
  }));
  mockUseOpportunityItems.mockImplementation(() => ({
    data: itemRows,
    refetch: vi.fn(),
  }));
  mockUseOpportunityItemDetail.mockImplementation((_: number | null, __: number | null, typeId: number | null) => ({
    data: typeId === null ? undefined : itemDetailsByType[typeId as keyof typeof itemDetailsByType],
    isLoading: false,
    refetch: vi.fn(),
  }));
});

afterEach(() => {
  vi.clearAllMocks();
});

test("renders trade page and applies default filters to item results", () => {
  renderPage();

  expect(screen.getByText("Regional Day Trader")).toBeInTheDocument();
  expect(screen.getByText("Source Markets")).toBeInTheDocument();
  const itemTable = screen.getAllByRole("table")[1];
  expect(within(itemTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(itemTable).queryByText("Pyerite")).not.toBeInTheDocument();
});

test("supports search, threshold changes, and sortable item rows", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.clear(screen.getByLabelText("Min ROI"));
  await user.type(screen.getByLabelText("Min ROI"), "0");
  await user.type(screen.getByLabelText("Item Search"), "pyer");

  const filteredTable = screen.getAllByRole("table")[1];
  expect(within(filteredTable).getByText("Pyerite")).toBeInTheDocument();
  expect(within(filteredTable).queryByText("Tritanium")).not.toBeInTheDocument();

  await user.clear(screen.getByLabelText("Item Search"));
  await user.click(screen.getByRole("button", { name: "Sort by Item Name" }));

  const table = screen.getAllByRole("table")[1];
  const rows = within(table).getAllByRole("row");
  expect(within(rows[1]).getByText("Pyerite")).toBeInTheDocument();
  expect(within(rows[2]).getByText("Tritanium")).toBeInTheDocument();
});

test("loads item detail for the selected row and updates when a different row is clicked", async () => {
  const user = userEvent.setup();
  renderPage();
  const detailPanel = screen.getByText("Execution Context").closest("section");

  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(1, 2, 34, 14);
  expect(detailPanel).not.toBeNull();
  expect(within(detailPanel as HTMLElement).getByText("Demand Source")).toBeInTheDocument();
  expect(within(detailPanel as HTMLElement).getByText("Adam4EVE")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("Min ROI"));
  await user.type(screen.getByLabelText("Min ROI"), "0");
  await user.click(within(screen.getAllByRole("table")[1]).getByText("Pyerite"));

  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(1, 2, 35, 14);
  expect(within(detailPanel as HTMLElement).getByText("Pyerite")).toBeInTheDocument();
  expect(within(detailPanel as HTMLElement).getByText("Fallback")).toBeInTheDocument();
});

test("requeries summaries and items when target or period changes and resets source selection", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(1, 14);
  expect(mockUseOpportunityItems).toHaveBeenLastCalledWith(1, 2, 14);

  const analysisPeriodInput = screen.getByLabelText("Analysis Period");
  await user.click(analysisPeriodInput);
  await user.keyboard("{Control>}a{/Control}30");
  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(1, 30);
  expect(mockUseOpportunityItems).toHaveBeenLastCalledWith(1, 2, 30);

  await user.selectOptions(screen.getByLabelText("Target Market"), "3");
  expect(mockUseSourceSummaries).toHaveBeenLastCalledWith(3, 30);
  expect(mockUseOpportunityItems).toHaveBeenLastCalledWith(3, 4, 30);
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(3, 4, 34, 30);
  expect(screen.getByText("Dodixie")).toBeInTheDocument();
});

test("renders stable empty states when no computed opportunities exist for the selected target", async () => {
  const user = userEvent.setup();
  mockUseSourceSummaries.mockImplementation((targetLocationId: number | null) => ({
    data: targetLocationId === 3 ? [] : targetLocationId === null ? [] : summaryRowsByTarget[targetLocationId] ?? [],
    refetch: vi.fn(),
  }));
  mockUseOpportunityItems.mockImplementation((targetLocationId: number | null, sourceLocationId: number | null) => ({
    data: targetLocationId === 3 || sourceLocationId === null ? [] : itemRows,
    refetch: vi.fn(),
  }));
  mockUseOpportunityItemDetail.mockImplementation(() => ({
    data: undefined,
    isLoading: false,
    refetch: vi.fn(),
  }));

  renderPage();

  await user.selectOptions(screen.getByLabelText("Target Market"), "3");

  expect(screen.getByText("No computed source markets available for this target yet.")).toBeInTheDocument();
  expect(screen.getByText("No computed item opportunities available for this source yet.")).toBeInTheDocument();
  expect(screen.getByText("Select an item to inspect its detail.")).toBeInTheDocument();
  expect(mockUseOpportunityItemDetail).toHaveBeenLastCalledWith(3, null, null, 14);
});

test("new filters: min profit, min margin pct, min demand/day, max DOS, min confidence, demand source, and min security", async () => {
  const user = userEvent.setup();
  renderPage();

  // Clear default min ROI so both items appear
  await user.clear(screen.getByLabelText("Min ROI"));
  await user.type(screen.getByLabelText("Min ROI"), "0");

  const itemTable = screen.getAllByRole("table")[1];
  expect(within(itemTable).getByText("Tritanium")).toBeInTheDocument();
  expect(within(itemTable).getByText("Pyerite")).toBeInTheDocument();

  // Min Profit filter — Tritanium has profit 12, Pyerite has profit 4
  await user.type(screen.getByLabelText("Min Profit"), "10");
  expect(within(screen.getAllByRole("table")[1]).getByText("Tritanium")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table")[1]).queryByText("Pyerite")).not.toBeInTheDocument();
  await user.clear(screen.getByLabelText("Min Profit"));

  // Min Demand/Day filter — Tritanium 12, Pyerite 16
  await user.clear(screen.getByLabelText("Min Demand Day"));
  await user.type(screen.getByLabelText("Min Demand Day"), "15");
  expect(within(screen.getAllByRole("table")[1]).queryByText("Tritanium")).not.toBeInTheDocument();
  expect(within(screen.getAllByRole("table")[1]).getByText("Pyerite")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Min Demand Day"));

  // Max DOS filter — Tritanium 1.5, Pyerite 2.5
  await user.type(screen.getByLabelText("Max DOS"), "2");
  expect(within(screen.getAllByRole("table")[1]).getByText("Tritanium")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table")[1]).queryByText("Pyerite")).not.toBeInTheDocument();
  await user.clear(screen.getByLabelText("Max DOS"));

  // Min Confidence filter — Tritanium 0.9, Pyerite 0.5
  await user.type(screen.getByLabelText("Min Confidence"), "0.8");
  expect(within(screen.getAllByRole("table")[1]).getByText("Tritanium")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table")[1]).queryByText("Pyerite")).not.toBeInTheDocument();
  await user.clear(screen.getByLabelText("Min Confidence"));

  // Source Type, Min Security, Demand Source selects render
  expect(screen.getByLabelText("Source Type")).toBeInTheDocument();
  expect(screen.getByLabelText("Min Security")).toBeInTheDocument();
  expect(screen.getByLabelText("Demand Source")).toBeInTheDocument();
});
