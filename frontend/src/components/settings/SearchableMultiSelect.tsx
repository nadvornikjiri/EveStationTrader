import { useEffect, useId, useMemo, useRef, useState } from "react";

type SearchableMultiSelectOption = {
  id: number;
  label: string;
  description?: string;
};

type SearchableMultiSelectProps = {
  title: string;
  placeholder: string;
  searchPlaceholder: string;
  emptyLabel: string;
  options: SearchableMultiSelectOption[];
  selectedIds: number[];
  onToggle: (id: number) => void;
};

export function SearchableMultiSelect({
  title,
  placeholder,
  searchPlaceholder,
  emptyLabel,
  options,
  selectedIds,
  onToggle,
}: SearchableMultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showAllChips, setShowAllChips] = useState(false);
  const [query, setQuery] = useState("");
  const searchId = useId();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const normalizedQuery = query.trim().toLowerCase();
  const selectedOptions = useMemo(
    () => options.filter((option) => selectedIds.includes(option.id)),
    [options, selectedIds],
  );
  const canSearch = normalizedQuery.length >= 4;
  const visibleOptions = useMemo(
    () =>
      options.filter((option) => {
        return `${option.label} ${option.description ?? ""}`.toLowerCase().includes(normalizedQuery);
      }),
    [normalizedQuery, options],
  );

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (rootRef.current === null || rootRef.current.contains(event.target as Node)) {
        return;
      }
      setIsOpen(false);
      setQuery("");
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const visibleChips = showAllChips ? selectedOptions : selectedOptions.slice(0, 3);
  const hiddenChipCount = Math.max(selectedOptions.length - visibleChips.length, 0);

  return (
    <div ref={rootRef} className="settings-multi-select">
      <div className="settings-multi-select__trigger">
        <div className="settings-multi-select__value" onClick={() => setIsOpen(true)}>
          {visibleChips.length > 0 ? (
            <>
              {visibleChips.map((option) => (
                <span key={option.id} className="settings-multi-select__chip">
                  <span className="settings-multi-select__chip-label">{option.label}</span>
                  <button
                    aria-label={`Remove ${option.label}`}
                    className="settings-multi-select__chip-remove"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onToggle(option.id);
                    }}
                  >
                    x
                  </button>
                </span>
              ))}
              {hiddenChipCount > 0 ? (
                <button
                  aria-label={`Show ${hiddenChipCount} more selected items`}
                  className="settings-multi-select__chip settings-multi-select__chip--summary"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setShowAllChips(true);
                  }}
                >
                  +{hiddenChipCount} more
                </button>
              ) : null}
            </>
          ) : (
            <span className="settings-multi-select__placeholder">{placeholder}</span>
          )}
        </div>
        <button
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-label={`Toggle ${title}`}
          className="settings-multi-select__toggle"
          type="button"
          onClick={() => setIsOpen((current) => !current)}
        >
          <span className="settings-multi-select__caret">{isOpen ? "▲" : "▼"}</span>
        </button>
      </div>
      {isOpen ? (
        <div className="settings-multi-select__panel">
          <label className="settings-multi-select__search" htmlFor={searchId}>
            <span className="sr-only">{title} search</span>
            <input
              id={searchId}
              aria-label={`${title} search`}
              placeholder={searchPlaceholder}
              type="search"
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="settings-multi-select__options" role="listbox" aria-label={title}>
            {!canSearch ? (
              <p className="settings-multi-select__empty">Type at least 4 characters to search.</p>
            ) : visibleOptions.length > 0 ? (
              visibleOptions.map((option) => {
                const isSelected = selectedIds.includes(option.id);
                return (
                  <button
                    key={option.id}
                    aria-selected={isSelected}
                    className="settings-multi-select__option"
                    role="option"
                    type="button"
                    onClick={() => onToggle(option.id)}
                  >
                    <span className={`settings-multi-select__check ${isSelected ? "is-selected" : ""}`}>
                      {isSelected ? "✓" : ""}
                    </span>
                    <span className="settings-multi-select__option-copy">
                      <span>{option.label}</span>
                      {option.description ? <span className="settings-multi-select__option-description">{option.description}</span> : null}
                    </span>
                  </button>
                );
              })
            ) : (
              <p className="settings-multi-select__empty">{emptyLabel}</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
