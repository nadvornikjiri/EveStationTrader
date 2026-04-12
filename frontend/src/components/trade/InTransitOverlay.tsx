import { useMemo, useState } from "react";

import type { InTransitAssetRecord, TargetLocation, TargetOpportunityItem } from "../../types/trade";

type Props = {
  target: TargetLocation | null;
  sourceOptions: TargetLocation[];
  itemOptions: TargetOpportunityItem[];
  entries: InTransitAssetRecord[];
  isOpen: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  errorMessage?: string | null;
  onToggleOpen: () => void;
  onSave: (payload: { source_location_id: number; target_location_id: number; type_id: number; quantity: number; note?: string }) => void;
  onDelete: (entryId: number) => void;
};

export function InTransitOverlay({
  target,
  sourceOptions,
  itemOptions,
  entries,
  isOpen,
  isSaving,
  isDeleting,
  errorMessage,
  onToggleOpen,
  onSave,
  onDelete,
}: Props) {
  const uniqueItemOptions = useMemo(() => {
    const deduped = new Map<number, TargetOpportunityItem>();
    for (const item of itemOptions) {
      if (!deduped.has(item.type_id)) {
        deduped.set(item.type_id, item);
      }
    }
    return [...deduped.values()].sort((left, right) => left.item_name.localeCompare(right.item_name));
  }, [itemOptions]);
  const [sourceLocationId, setSourceLocationId] = useState("");
  const [typeId, setTypeId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [note, setNote] = useState("");

  if (target === null) {
    return null;
  }

  const handleSubmit = () => {
    const parsedSourceLocationId = Number.parseInt(sourceLocationId, 10);
    const parsedTypeId = Number.parseInt(typeId, 10);
    const parsedQuantity = Number.parseInt(quantity, 10);
    if (!Number.isFinite(parsedSourceLocationId) || !Number.isFinite(parsedTypeId) || !Number.isFinite(parsedQuantity)) {
      return;
    }
    onSave({
      source_location_id: parsedSourceLocationId,
      target_location_id: target.location_id,
      type_id: parsedTypeId,
      quantity: Math.max(parsedQuantity, 1),
      note: note.trim() || undefined,
    });
    setQuantity("1");
    setNote("");
  };

  if (!isOpen) {
    return (
      <div
        className="in-transit-tab"
        onClick={onToggleOpen}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            onToggleOpen();
          }
        }}
      >
        <span className="in-transit-tab__count">{entries.length}</span>
        <span className="in-transit-tab__label">In Transit</span>
        <span className="in-transit-tab__chevron">▲</span>
      </div>
    );
  }

  return (
    <div className="in-transit-overlay">
      <div className="in-transit-overlay__header">
        <div>
          <span className="shopping-list-overlay__title">In Transit</span>
          <p className="in-transit-overlay__subtitle">Target: {target.name}</p>
        </div>
        <button type="button" className="shopping-list-overlay__minimize-btn" onClick={onToggleOpen} aria-label="Minimize in-transit overlay">
          ▼
        </button>
      </div>
      <div className="in-transit-overlay__body">
        <div className="in-transit-form">
          <label>
            Source
            <select value={sourceLocationId} onChange={(event) => setSourceLocationId(event.target.value)}>
              <option value="">Select source</option>
              {sourceOptions.map((source) => (
                <option key={source.location_id} value={source.location_id}>
                  {source.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Item
            <select value={typeId} onChange={(event) => setTypeId(event.target.value)}>
              <option value="">Select item</option>
              {uniqueItemOptions.map((item) => (
                <option key={item.type_id} value={item.type_id}>
                  {item.item_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Quantity
            <input type="number" min={1} value={quantity} onChange={(event) => setQuantity(event.target.value)} />
          </label>
          <label>
            Note
            <input type="text" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional" />
          </label>
          <button
            type="button"
            className="shopping-list-overlay__export-btn"
            disabled={isSaving || sourceLocationId.length === 0 || typeId.length === 0}
            onClick={handleSubmit}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
        {errorMessage ? <p role="alert">{errorMessage}</p> : null}
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Item</th>
                <th>Quantity</th>
                <th>Note</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={5}>No in-transit assets tracked for this target.</td>
                </tr>
              ) : (
                entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.source_market_name}</td>
                    <td>{entry.item_name}</td>
                    <td>{entry.quantity}</td>
                    <td>{entry.note ?? "—"}</td>
                    <td>
                      <button
                        type="button"
                        className="shopping-list-remove-btn"
                        disabled={isDeleting}
                        onClick={() => onDelete(entry.id)}
                        aria-label={`Remove in-transit entry for ${entry.item_name}`}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
