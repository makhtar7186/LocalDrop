const UNITS = ["o", "Ko", "Mo", "Go", "To"] as const;

/** Taille lisible en français (base 1024) : 1,5 Mo. */
export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: digits })} ${UNITS[unit]}`;
}

export function formatSpeed(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`;
}

export function percent(done: number, total: number): number {
  if (total <= 0) return 100;
  return Math.min(100, Math.floor((done / total) * 100));
}

const DATE_FORMAT = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** Date courte en heure locale : « 20/11 14:05 ». Les dates serveur sont en UTC. */
export function formatDate(iso: string): string {
  const withZone = /[zZ]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(withZone);
  return Number.isNaN(date.getTime()) ? "" : DATE_FORMAT.format(date).replace(",", "");
}
