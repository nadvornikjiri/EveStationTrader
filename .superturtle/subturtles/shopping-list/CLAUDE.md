# Current task

Test the full flow manually: add items, edit qty, verify totals, export multibuy, clear, minimize/expand.

# End goal with specs

## Feature overview
A shopping list overlay on the Trade Page that lets users select items from the source summary table, accumulate them in a list with editable quantities, see totals, and export to Eve multibuy format.

## Detailed specs

### 1. Add-to-list checkbox in SourceSummaryTable
- Add a checkbox column as the FIRST column in the expanded item rows (inside SourceSummaryTable.tsx)
- Checkbox toggles item in/out of the shopping list
- Checked state reflects whether the item's type_id is in the shopping list
- Update all colSpan values accordingly (+1)

### 2. Shopping list state (TradePage.tsx)
- Session-only state (useState, no localStorage)
- State shape: ShoppingListEntry[] where each entry has:
  - type_id: number
  - item_name: string
  - quantity: number (default = Math.floor(item.target_demand_day), minimum 1)
  - source_station_sell_price: number
  - item_volume_m3: number
  - target_demand_day: number (needed for "days of demand" column)
  - source_station_name: string (from the parent SourceSummary row)
- Unchecking the checkbox removes the item from the list
- Shopping list tracks source_station_name from the first item added; displayed in the overlay title
- Multiple source stations allowed (user can switch targets, come back, add more)

### 3. ShoppingListOverlay component (NEW: frontend/src/components/trade/ShoppingListOverlay.tsx)
- Fixed to viewport bottom (position: fixed; bottom: 0; left: 0; right: 0; z-index high)
- Two states: minimized (tab bar) and expanded (full panel)
- **Minimized tab bar**: shows item count + "Shopping List" label, click to expand. Always visible when list has items.
- **Expanded panel**: 
  - Title: "Shopping List — {source_station_name}" (or multiple station names if items from different sources). Title clears when list is empty.
  - Top-right summary bar: Total Price (ISK formatted), Total Volume (m³), "Export to Multibuy" button, "Clear All" button
  - Table with columns: Item Name, Quantity (editable input), Days of Demand (quantity / target_demand_day, show 1 decimal), Total Price (quantity * source_station_sell_price), Total Volume m³ (quantity * item_volume_m3), Remove (X button)
  - Editing quantity recalculates Total Price, Total Volume, Days of Demand, and summary totals
  - Max height with overflow-y scroll for large lists
  - Click minimize button to collapse back to tab bar

### 4. Export to Multibuy
- Format: one line per item, "ItemName Quantity\n" (space-separated, integer quantities)
- Example: "Tritanium 500\nMexallon 200"
- navigator.clipboard.writeText() 
- Brief "Copied!" feedback on button (1.5s timeout)

### 5. Clear All button
- Next to the Export button in the summary bar
- Clears entire shopping list, collapses overlay

## File ownership
- YOU OWN: frontend/src/pages/TradePage.tsx
- YOU OWN: frontend/src/components/trade/SourceSummaryTable.tsx
- YOU OWN: frontend/src/components/trade/ShoppingListOverlay.tsx (NEW)
- YOU OWN: frontend/src/types/trade.ts
- YOU OWN: frontend/src/styles/global.css
- READ ONLY: backend/app/api/schemas/trade.py (for reference on available fields)

## Key data fields available per item row (OpportunityItemRow from API):
- type_id, item_name, target_demand_day, source_station_sell_price, item_volume_m3
- The parent SourceSummary row has: source_location_name (use this as source_station_name)

## UI framework
- Plain React + custom CSS (global.css). No MUI, no Tailwind.
- BEM-ish class names. Dark theme with CSS variables (--bg-primary, --text-primary, --accent, --border, etc.)
- Tables use standard HTML <table> elements
- Match existing visual style exactly

# Roadmap (Completed)
- Requirements gathered and clarified

# Roadmap (Upcoming)
- Implement shopping list feature end to end
- Commit with descriptive message

# Backlog
- [x] Add ShoppingListEntry type to frontend/src/types/trade.ts
- [x] Add shopping list state + handlers to TradePage.tsx (useState for entries + open/closed, handler functions for add/remove/updateQty/clear/export)
- [x] Add checkbox column to SourceSummaryTable.tsx item rows (first column, pass shoppingListTypeIds Set and onToggleShoppingList callback as props)
- [x] Create ShoppingListOverlay.tsx component with minimized tab + expanded panel + summary bar + table with editable qty + days of demand + remove buttons
- [x] Add CSS styles to global.css for the overlay (fixed positioning, dark theme, minimize/expand transitions, scrollable table)
- [x] Wire ShoppingListOverlay into TradePage.tsx, pass all props (entries, isOpen, onToggleOpen, onRemove, onUpdateQty, onClearAll, onExportMultibuy)
- [ ] Test the full flow manually: add items, edit qty, verify totals, export multibuy, clear, minimize/expand <- current
- [ ] Commit all changes with descriptive message
