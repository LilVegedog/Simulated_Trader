const money = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const fmtPrice = (n: number) => money.format(n);

export const fmtMoney = (n: number) => `$${money.format(n)}`;

export const fmtSignedMoney = (n: number) =>
  `${n < 0 ? "-" : "+"}$${money.format(Math.abs(n))}`;

export const fmtPercent = (n: number) => `${n < 0 ? "" : "+"}${n.toFixed(2)}%`;

export const fmtQty = (n: number) =>
  Number.isInteger(n) ? String(n) : n.toFixed(4).replace(/0+$/, "");

export const pnlColor = (n: number) =>
  n > 0 ? "text-up" : n < 0 ? "text-down" : "text-ink-dim";
