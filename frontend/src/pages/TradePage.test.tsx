import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { TradePage } from "./TradePage";

vi.mock("../hooks/useTradeData", () => ({
  useTargets: () => ({ data: [{ location_id: 1, name: "Jita", location_type: "npc_station", region_name: "The Forge", system_name: "Jita" }] }),
  useSourceSummaries: () => ({
    data: [
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
        risk_pct_weighted: 0.08,
        warning_count: 0,
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
    refetch: vi.fn(),
  }),
  useOpportunityItems: () => ({
    data: [
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
        risk_pct: 0.08,
        warning_flag: false,
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
    ],
  }),
}));

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

test("renders trade page shell and data tables", () => {
  renderPage();
  expect(screen.getByText("Regional Day Trader")).toBeInTheDocument();
  expect(screen.getByText("Source Markets")).toBeInTheDocument();
  expect(screen.getByText("Tritanium")).toBeInTheDocument();
});
