export function formatNumber(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) {
    return "0";
  }

  if (Math.abs(number) >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(1)}M`;
  }

  if (Math.abs(number) >= 1_000) {
    return `${(number / 1_000).toFixed(1)}k`;
  }

  return number.toLocaleString();
}

export function formatInteger(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) {
    return "0";
  }
  return Math.round(number).toLocaleString();
}

export function formatCurrency(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) {
    return "$0.00";
  }
  return `$${number.toFixed(number < 10 ? 3 : 2)}`;
}

export function formatPercent(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) {
    return "0%";
  }
  return `${number.toFixed(number >= 100 ? 0 : 1)}%`;
}

export function formatDurationMs(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) {
    return "0 ms";
  }
  if (number >= 1000) {
    return `${(number / 1000).toFixed(2)}s`;
  }
  return `${Math.round(number)}ms`;
}

export function formatRelativeTime(timestamp) {
  if (!timestamp) {
    return "—";
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  const diffMs = Date.now() - date.getTime();
  const diffSeconds = Math.max(0, Math.floor(diffMs / 1000));

  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
