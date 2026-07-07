// The canonical list of dollar-savings sources backing the "lifetime"
// (and session) savings dicts returned by savings_tracker.py. Each entry
// pairs the raw lifetime/session field name with its `savings_by_source`
// attribution key. A single "Money saved" figure must sum every source
// here, not just compression, or it silently undercounts cache/routing/
// schema savings relative to per-source attribution panels.
export const LIFETIME_SAVINGS_SOURCES = [
  ['compression_savings_usd', 'cutctx_compression'],
  ['cache_savings_usd', 'provider_prompt_cache'],
  ['semantic_cache_savings_usd', 'semantic_cache'],
  ['self_hosted_prefix_cache_savings_usd', 'prefix_cache_self_hosted'],
  ['model_routing_savings_usd', 'model_routing'],
  ['tool_schema_compaction_savings_usd', 'tool_schema_compaction'],
  ['api_surface_slimming_savings_usd', 'api_surface_slimming'],
  ['normalization_savings_usd', 'normalization'],
  ['batch_routing_savings_usd', 'batch_routing'],
  ['memoization_savings_usd', 'memoization'],
  ['output_optimization_savings_usd', 'output_optimization'],
];

export function sumSavingsUsd(record) {
  return LIFETIME_SAVINGS_SOURCES.reduce(
    (sum, [key]) => sum + Number(record?.[key] || 0),
    0,
  );
}

export function sumSavingsObservedUsd(record) {
  return LIFETIME_SAVINGS_SOURCES.reduce(
    (sum, [key]) => sum + Number(record?.[key.replace('_usd', '_observed_usd')] || 0),
    0,
  );
}

// `record` is either a lifetime/session-shaped dict (sum every source), or
// a period-bucket aggregate from `aggregatePeriodBuckets` which already
// precomputes `total_savings_usd` across all sources.
export function getDurationSavingsUsd(record) {
  if (!record) {
    return 0;
  }
  if (record.total_savings_usd != null) {
    return Number(record.total_savings_usd) || 0;
  }
  return sumSavingsUsd(record);
}
