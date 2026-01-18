/**
 * Format a decimal probability as a percentage string
 * @param value - Decimal probability (0-1)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string (e.g., "83.0%")
 */
export function formatPercent(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a large number with comma separators
 * @param value - The number to format
 * @returns Formatted number string (e.g., "1,429,000")
 */
export function formatNumber(value: number): string {
  return value.toLocaleString('en-US');
}

/**
 * Format a confidence interval range
 * @param low - Lower bound (0-1)
 * @param high - Upper bound (0-1)
 * @returns Formatted CI string (e.g., "82% - 84%")
 */
export function formatCI(low: number, high: number): string {
  return `${Math.round(low * 100)}% - ${Math.round(high * 100)}%`;
}

/**
 * Format a currency value for Iranian Rial
 * @param value - The rial amount
 * @returns Formatted currency string
 */
export function formatRial(value: number): string {
  return `${formatNumber(value)} IRR`;
}

/**
 * Format a day number for display
 * @param day - Day number (0-90)
 * @returns Formatted day string (e.g., "Day 45")
 */
export function formatDay(day: number): string {
  return `Day ${day}`;
}
