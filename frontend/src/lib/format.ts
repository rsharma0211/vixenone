/**
 * Currency formatting utilities for VixenOne.
 * Never imports mockData.
 */

export function formatINR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) {
    return 'Not stated';
  }
  const formatted = new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 0,
  }).format(amount);
  return `₹${formatted}`;
}
