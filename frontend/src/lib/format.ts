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

/**
 * Decimal-safe round half-up formatting to 1 decimal place.
 * Avoids JS toFixed() banker's rounding and float representation bugs.
 * e.g. 29.05 -> "29.1", 23.44 -> "23.4", 35 -> "35.0"
 */
export function formatPointsHalfUp(points: number | string | null | undefined): string {
  if (points === null || points === undefined || points === '') {
    return '—';
  }
  const str = String(points).trim();
  if (str === '' || isNaN(Number(str))) {
    return '—';
  }

  const isNegative = str.startsWith('-');
  const cleanStr = isNegative ? str.slice(1) : str;

  const [intPart = '0', decPart = ''] = cleanStr.split('.');

  if (decPart.length === 0) {
    return `${isNegative ? '-' : ''}${intPart}.0`;
  }

  if (decPart.length === 1) {
    return `${isNegative ? '-' : ''}${intPart}.${decPart}`;
  }

  // Decimal part has >= 2 digits: inspect the second digit for half-up rounding
  const d1 = parseInt(decPart[0], 10);
  const d2 = parseInt(decPart[1], 10);

  let roundedD1 = d1;
  let carry = 0;

  if (d2 >= 5) {
    roundedD1 += 1;
    if (roundedD1 === 10) {
      roundedD1 = 0;
      carry = 1;
    }
  }

  if (carry > 0) {
    try {
      const newInt = BigInt(intPart) + BigInt(1);
      return `${isNegative ? '-' : ''}${newInt.toString()}.${roundedD1}`;
    } catch {
      const newInt = parseInt(intPart, 10) + 1;
      return `${isNegative ? '-' : ''}${newInt}.${roundedD1}`;
    }
  }

  return `${isNegative ? '-' : ''}${intPart}.${roundedD1}`;
}

/**
 * Format date for print report header in DD Mon YYYY format.
 */
export function formatPrintDate(date: Date = new Date()): string {
  const day = String(date.getDate()).padStart(2, '0');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[date.getMonth()];
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
}

