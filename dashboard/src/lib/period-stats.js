// stats-history's `history_summary` field is compaction metadata
// ({mode, stored_points, returned_points, compacted}), not a period
// aggregate — it's always a truthy object, so naively doing
// `data.history_summary || data.lifetime` silently picks it every time and
// every duration tab renders zeros. Real bucketed stats live under
// `series.{hourly,daily,weekly,monthly}`, one entry per active bucket with
// per-bucket deltas (`tokens_saved`, `compression_savings_usd_delta`, etc.)
// plus a `by_model` breakdown. This aggregates the buckets that fall inside
// the requested lookback window.

export const PERIOD_WINDOW_MS = {
  daily: 24 * 60 * 60 * 1000,
  weekly: 7 * 24 * 60 * 60 * 1000,
  monthly: 30 * 24 * 60 * 60 * 1000,
};

export const PERIOD_SERIES_KEY = {
  daily: 'hourly',
  weekly: 'daily',
  monthly: 'daily',
};

// Non-compression savings sources also carry a per-checkpoint delta in
// each bucket (see savings_tracker.py `_build_rollup`). Without summing
// these too, a period tab's "money saved" would only reflect compression
// and silently drop cache/routing/schema savings for the window.
const EXTRA_SAVINGS_SOURCE_DELTA_KEYS = [
  'cache_savings_usd_delta',
  'semantic_cache_savings_usd_delta',
  'self_hosted_prefix_cache_savings_usd_delta',
  'model_routing_savings_usd_delta',
  'tool_schema_compaction_savings_usd_delta',
  'api_surface_slimming_savings_usd_delta',
];

export function aggregatePeriodBuckets(buckets, windowMs) {
  const cutoff = Date.now() - windowMs;
  const inWindow = buckets.filter((b) => new Date(b.timestamp).getTime() >= cutoff);

  const summary = {
    requests: 0,
    tokens_saved: 0,
    compression_savings_usd: 0,
    other_savings_usd: 0,
    total_savings_usd: 0,
    total_input_tokens: 0,
    total_input_cost_usd: 0,
    models: {},
  };

  for (const bucket of inWindow) {
    summary.requests += bucket.requests || 0;
    summary.tokens_saved += bucket.tokens_saved || 0;
    summary.compression_savings_usd += bucket.compression_savings_usd_delta || 0;
    summary.total_input_tokens += bucket.total_input_tokens_delta || 0;
    summary.total_input_cost_usd += bucket.total_input_cost_usd_delta || 0;

    for (const key of EXTRA_SAVINGS_SOURCE_DELTA_KEYS) {
      summary.other_savings_usd += bucket[key] || 0;
    }

    for (const [model, data] of Object.entries(bucket.by_model || {})) {
      const entry = summary.models[model] || { tokens_saved: 0, compression_savings_usd: 0 };
      entry.tokens_saved += data.tokens_saved || 0;
      entry.compression_savings_usd += data.compression_savings_usd_delta || 0;
      summary.models[model] = entry;
    }
  }

  summary.total_savings_usd = summary.compression_savings_usd + summary.other_savings_usd;
  summary.savings_percent = summary.total_input_tokens > 0
    ? (summary.tokens_saved / summary.total_input_tokens) * 100
    : 0;

  return summary;
}

// Fetches /stats-history for a non-lifetime, non-session duration and
// returns the correctly time-windowed aggregate (see note above on why
// this can't just read `data.history_summary`).
export async function fetchPeriodStats(fetchDashboardJson, duration) {
  const data = await fetchDashboardJson(`/stats-history?series=${duration}`);
  const seriesKey = PERIOD_SERIES_KEY[duration];
  const buckets = data?.series?.[seriesKey] || [];
  return aggregatePeriodBuckets(buckets, PERIOD_WINDOW_MS[duration]);
}
