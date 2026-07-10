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

export const OBSERVED_PROVIDER_SAVINGS_SOURCES = LIFETIME_SAVINGS_SOURCES.filter(
  ([, source]) => source === 'provider_prompt_cache',
);

export const CREATED_SAVINGS_SOURCES = LIFETIME_SAVINGS_SOURCES.filter(
  ([, source]) => source !== 'provider_prompt_cache',
);

function sumSavingsForSources(record, sources) {
  return sources.reduce((sum, [key]) => sum + Number(record?.[key] || 0), 0);
}

function sumObservedSavingsForSources(record, sources) {
  return sources.reduce(
    (sum, [key]) => sum + Number(record?.[key.replace('_usd', '_observed_usd')] || 0),
    0,
  );
}

export function sumSavingsUsd(record) {
  return sumSavingsForSources(record, LIFETIME_SAVINGS_SOURCES);
}

export function sumSavingsObservedUsd(record) {
  return sumObservedSavingsForSources(record, LIFETIME_SAVINGS_SOURCES);
}

export function sumCreatedSavingsUsd(record) {
  return sumSavingsForSources(record, CREATED_SAVINGS_SOURCES);
}

export function sumCreatedSavingsObservedUsd(record) {
  return sumObservedSavingsForSources(record, CREATED_SAVINGS_SOURCES);
}

export function sumObservedProviderSavingsUsd(record) {
  return sumSavingsForSources(record, OBSERVED_PROVIDER_SAVINGS_SOURCES);
}

export function sumObservedProviderSavingsObservedUsd(record) {
  return sumObservedSavingsForSources(record, OBSERVED_PROVIDER_SAVINGS_SOURCES);
}

function pickFirstNumeric(record, keys) {
  for (const key of keys) {
    if (record?.[key] == null) {
      continue;
    }

    const value = Number(record[key]);
    if (Number.isFinite(value)) {
      return value;
    }
  }

  return null;
}

export function getCreatedObservedSavingsUsd(record, fallbackRecord = null) {
  const createdUsd = pickFirstNumeric(record, [
    'created_savings_usd',
    'createdSavingsUsd',
    'created_usd',
  ]);
  const observedUsd = pickFirstNumeric(record, [
    'observed_provider_savings_usd',
    'observedProviderSavingsUsd',
    'observed_usd',
  ]);

  const recordCreatedUsd = sumCreatedSavingsUsd(record);
  const recordObservedUsd = sumObservedProviderSavingsUsd(record);
  const fallbackCreatedUsd = sumCreatedSavingsUsd(fallbackRecord);
  const fallbackObservedUsd = sumObservedProviderSavingsUsd(fallbackRecord);

  return {
    createdUsd: createdUsd != null ? createdUsd : recordCreatedUsd || fallbackCreatedUsd,
    observedUsd: observedUsd != null ? observedUsd : recordObservedUsd || fallbackObservedUsd,
  };
}

export function getCreatedObservedSavingsTokens(record, sourceRows = []) {
  const explicitCreated = pickFirstNumeric(record, [
    'created_savings_tokens',
    'createdSavingsTokens',
  ]);
  const explicitObserved = pickFirstNumeric(record, [
    'observed_provider_savings_tokens',
    'observedProviderSavingsTokens',
  ]);
  const providerRow = sourceRows.find((row) => row.key === 'provider_prompt_cache');
  const attributedTotal = sourceRows.reduce((sum, row) => sum + Number(row.tokens || 0), 0);
  const observedFallback = Number(providerRow?.tokens || 0);
  const createdFallback = attributedTotal > 0
    ? Math.max(attributedTotal - observedFallback, 0)
    : Math.max(Number(record?.tokens_saved || 0), 0);
  const hasCoveredRequests = Number(record?.attribution_coverage?.attributed_requests || 0) > 0;
  const explicitTotalsAreUsable = hasCoveredRequests
    || Number(explicitCreated || 0) + Number(explicitObserved || 0) > 0
    || Number(record?.tokens_saved || 0) === 0;
  return {
    createdTokens: explicitCreated != null && explicitTotalsAreUsable
      ? explicitCreated
      : createdFallback,
    observedTokens: explicitObserved != null && explicitTotalsAreUsable
      ? explicitObserved
      : observedFallback,
    explicit: explicitCreated != null && explicitObserved != null && explicitTotalsAreUsable,
  };
}

export function getAttributionCoverage(record) {
  const coverage = record?.attribution_coverage || {};
  const attributedRequests = Number(coverage.attributed_requests || 0);
  const legacyRequests = Number(coverage.legacy_unattributed_requests || 0);
  const total = attributedRequests + legacyRequests;
  const percent = coverage.coverage_percent != null
    ? Number(coverage.coverage_percent)
    : total > 0
      ? (attributedRequests / total) * 100
      : 100;
  return {
    attributedRequests,
    legacyRequests,
    percent,
    complete: coverage.complete != null ? Boolean(coverage.complete) : legacyRequests === 0,
  };
}

export function getCreatedSavingsRate(createdTokens, inputTokens) {
  const created = Math.max(Number(createdTokens || 0), 0);
  const input = Math.max(Number(inputTokens || 0), 0);
  const counterfactual = input + created;
  return counterfactual > 0 ? (created / counterfactual) * 100 : 0;
}

export function isVisibleSavingsRow(row) {
  if (!row) {
    return false;
  }

  return Boolean(
    row.active
      || row.enabled
      || row.explicitlyEnabled
      || Number(row.tokens || 0) > 0
      || Number(row.usd || 0) > 0,
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
