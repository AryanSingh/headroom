export type CommunityStats = {
  total_tokens_saved: number;
  total_cost_saved: number;
  total_requests: number;
  unique_instances: number;
};

const PUBLISHED_SNAPSHOT: CommunityStats = {
  total_tokens_saved: 41750654085,
  total_cost_saved: 176635.62,
  total_requests: 1194154,
  unique_instances: 889,
};

export async function fetchCommunityStats(): Promise<CommunityStats> {
  // The docs site currently renders a published community snapshot rather than
  // performing a live fetch at build/render time. Keep the async contract so a
  // real remote fetch can be introduced later without changing callers.
  return PUBLISHED_SNAPSHOT;
}

export function fmtNum(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

export function fmtUsd(value: number): string {
  if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}
