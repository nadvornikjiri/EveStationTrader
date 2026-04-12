import { useState } from "react";

import type { ShoppingListEntry } from "../../types/trade";

type Props = {
  entries: ShoppingListEntry[];
  isOpen: boolean;
  onToggleOpen: () => void;
  onRemove: (typeId: number) => void;
  onUpdateQty: (typeId: number, quantity: number) => void;
  onClearAll: () => void;
  onExportMultibuy: () => void;
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

export function ShoppingListOverlay({
  entries,
  isOpen,
  onToggleOpen,
  onRemove,
  onUpdateQty,
  onClearAll,
  onExportMultibuy,
}: Props) {
  const [copied, setCopied] = useState(false);

  if (entries.length === 0) {
    return null;
  }

  const stationNames = [...new Set(entries.map((e) => e.source_station_name))];
  const title = stationNames.length > 0 ? `Shopping List — ${stationNames.join(", ")}` : "Shopping List";

  const totalPrice = entries.reduce((sum, e) => sum + e.quantity * e.source_station_sell_price, 0);
  const totalVolume = entries.reduce((sum, e) => sum + e.quantity * e.item_volume_m3, 0);

  const handleExport = () => {
    onExportMultibuy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleClearAll = () => {
    onClearAll();
  };

  if (!isOpen) {
    return (
      <div className="shopping-list-tab" onClick={onToggleOpen} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onToggleOpen(); }}>
        <span className="shopping-list-tab__count">{entries.length}</span>
        <span className="shopping-list-tab__label">Shopping List</span>
        <span className="shopping-list-tab__chevron">▲</span>
      </div>
    );
  }

  return (
    <div className="shopping-list-overlay">
      <div className="shopping-list-overlay__header">
        <span className="shopping-list-overlay__title">{title}</span>
        <div className="shopping-list-overlay__summary-bar">
          <span className="shopping-list-overlay__total">
            <span className="shopping-list-overlay__total-label">Total:</span>
            <span className="shopping-list-overlay__total-price">{formatIsk(totalPrice)}</span>
            <span className="shopping-list-overlay__total-volume">{formatVolume(totalVolume)}</span>
          </span>
          <button
            type="button"
            className="shopping-list-overlay__export-btn"
            onClick={handleExport}
          >
            {copied ? "Copied!" : "Export to Multibuy"}
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
            onClick={onToggleOpen}
            aria-label="Minimize shopping list"
          >
            ▼
          </button>
        </div>
      </div>
      <div className="shopping-list-overlay__body">
        <table className="data-table shopping-list-table">
          <thead>
            <tr>
              <th>Item Name</th>
              <th>Quantity</th>
              <th>Days of Demand</th>
              <th>Total Price</th>
              <th>Total Volume</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const rowTotal = entry.quantity * entry.source_station_sell_price;
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
                  <td>{formatIsk(rowTotal)}</td>
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
  );
}
