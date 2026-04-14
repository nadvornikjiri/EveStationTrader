import { useState } from "react";

import type { ShoppingListEntry } from "../../types/trade";

type Props = {
  entries: ShoppingListEntry[];
  isOpen: boolean;
  onRemove: (typeId: number) => void;
  onUpdateQty: (typeId: number, quantity: number) => void;
  onClearAll: () => void;
  onExportMultibuy: () => Promise<boolean>;
  onMinimize: () => void;
};

function formatIsk(value: number): string {
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B ISK`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M ISK`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(2)}K ISK`;
  }
  return `${value.toLocaleString()} ISK`;
}

function formatVolume(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M m³`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(2)}K m³`;
  }
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} m³`;
}

function metricToneClass(value: number): string | null {
  if (value > 0) {
    return "metric-cell-positive";
  }
  if (value < 0) {
    return "metric-cell-negative";
  }
  return null;
}

export function ShoppingListOverlay({
  entries,
  isOpen,
  onRemove,
  onUpdateQty,
  onClearAll,
  onExportMultibuy,
  onMinimize,
}: Props) {
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  if (entries.length === 0) {
    return null;
  }

  const stationNames = [...new Set(entries.map((e) => e.source_station_name))];
  const title = stationNames.length > 0 ? `Shopping List — ${stationNames.join(", ")}` : "Shopping List";

  const totalPrice = entries.reduce((sum, e) => sum + e.quantity * e.source_station_sell_price, 0);
  const totalTargetNowProfit = entries.reduce((sum, e) => sum + e.quantity * e.target_now_profit, 0);
  const totalTargetPeriodProfit = entries.reduce((sum, e) => sum + e.quantity * e.target_period_profit, 0);
  const totalVolume = entries.reduce((sum, e) => sum + e.quantity * e.item_volume_m3, 0);

  const handleExport = async () => {
    const success = await onExportMultibuy();
    if (success) {
      setToast({ message: "Copied to clipboard", type: "success" });
    } else {
      setToast({ message: "Failed to copy to clipboard", type: "error" });
    }
    setTimeout(() => setToast(null), 2500);
  };

  const handleClearAll = () => {
    onClearAll();
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="shopping-list-overlay">
      <div className="shopping-list-overlay__header">
        <span className="shopping-list-overlay__title">{title}</span>
        <div className="shopping-list-overlay__summary-bar">
          <span className="shopping-list-overlay__total">
            <span className="shopping-list-overlay__total-label">Total Price:</span>
            <span className="shopping-list-overlay__total-price metric-cell-source-price">{formatIsk(totalPrice)}</span>
            <span className="shopping-list-overlay__total-label">Total Now Profit:</span>
            <span className={`shopping-list-overlay__total-price ${metricToneClass(totalTargetNowProfit) ?? ""}`.trim()}>
              {formatIsk(totalTargetNowProfit)}
            </span>
            <span className="shopping-list-overlay__total-label">Total Period Profit:</span>
            <span className={`shopping-list-overlay__total-price ${metricToneClass(totalTargetPeriodProfit) ?? ""}`.trim()}>
              {formatIsk(totalTargetPeriodProfit)}
            </span>
            <span className="shopping-list-overlay__total-volume">{formatVolume(totalVolume)}</span>
          </span>
          <button
            type="button"
            className="shopping-list-overlay__export-btn"
            onClick={() => { void handleExport(); }}
          >
            Export to Multibuy
          </button>
          <button
            type="button"
            className="shopping-list-overlay__clear-btn clear-button"
            onClick={handleClearAll}
          >
            Clear All
          </button>
          <button
            type="button"
            className="shopping-list-overlay__minimize-btn"
            onClick={onMinimize}
            aria-label="Minimize shopping list"
          >
            ▼
          </button>
        </div>
      </div>
      <div className="shopping-list-overlay__body">
        <div className="table-scroll">
          <table className="data-table shopping-list-table">
            <thead>
              <tr>
                <th>Item Name</th>
                <th>Quantity</th>
                <th>Days of Demand</th>
                <th>Total Price</th>
                <th>Target Now Profit</th>
                <th>Target Period Profit</th>
                <th>Total Volume</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const rowTotal = entry.quantity * entry.source_station_sell_price;
                const rowTargetNowProfit = entry.quantity * entry.target_now_profit;
                const rowTargetPeriodProfit = entry.quantity * entry.target_period_profit;
                const rowVolume = entry.quantity * entry.item_volume_m3;
                const daysOfDemand = entry.target_demand_day > 0
                  ? (entry.quantity / entry.target_demand_day).toFixed(1)
                  : "—";

                return (
                  <tr key={entry.type_id}>
                    <td>{entry.item_name}</td>
                    <td>
                      <input
                        className="shopping-list-qty-input"
                        type="number"
                        min={1}
                        value={entry.quantity}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          if (!isNaN(val) && val >= 1) {
                            onUpdateQty(entry.type_id, val);
                          }
                        }}
                      />
                    </td>
                    <td>{daysOfDemand}</td>
                    <td className="metric-cell-source-price">{formatIsk(rowTotal)}</td>
                    <td className={metricToneClass(rowTargetNowProfit) ?? undefined}>{formatIsk(rowTargetNowProfit)}</td>
                    <td className={metricToneClass(rowTargetPeriodProfit) ?? undefined}>{formatIsk(rowTargetPeriodProfit)}</td>
                    <td>{formatVolume(rowVolume)}</td>
                    <td>
                      <button
                        type="button"
                        className="shopping-list-remove-btn"
                        onClick={() => onRemove(entry.type_id)}
                        aria-label={`Remove ${entry.item_name}`}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {toast ? (
        <div className={`shopping-list-toast shopping-list-toast--${toast.type}`}>
          {toast.message}
        </div>
      ) : null}
    </div>
  );
}
