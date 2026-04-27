/**
 * Compact number formatting helpers used across the trade UI.
 *
 * Rules:
 *   >= 1B   -> "1.23B"
 *   >= 1M   -> "1.23M"
 *   >= 1K   -> "1.23K"  (ISK only; volumes show full number below 1M)
 *   < 1K    -> locale-formatted integer
 *
 * Negative values are handled (the sign is preserved).
 */

function compactAbs(abs: number, thresholds: { k: boolean }): string {
  if (abs >= 1_000_000_000) {
    return `${(abs / 1_000_000_000).toFixed(2)}B`;
  }
  if (abs >= 1_000_000) {
    return `${(abs / 1_000_000).toFixed(2)}M`;
  }
  if (thresholds.k && abs >= 1_000) {
    return `${(abs / 1_000).toFixed(2)}K`;
  }
  return Math.round(abs).toLocaleString();
}

/** Format an ISK value: 1,234,567 -> "1.23M" */
export function formatIsk(value: number): string {
  if (value === 0) return "0";
  const sign = value < 0 ? "-" : "";
  return `${sign}${compactAbs(Math.abs(value), { k: true })}`;
}

/** Format a volume in m3: 1,234,567 -> "1.23M m3" */
export function formatVolume(value: number): string {
  if (value === 0) return "0 m3";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toFixed(2)}M m3`;
  }
  if (abs >= 1_000) {
    return `${sign}${(abs / 1_000).toFixed(2)}K m3`;
  }
  return `${sign}${Math.round(abs).toLocaleString()} m3`;
}

/** Format a percentage: 0.25 -> "25%" */
export function formatWholePercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Format a quantity (no suffix, full integers): 1234 -> "1,234" */
export function formatQuantity(value: number): string {
  return Math.round(value).toLocaleString();
}
