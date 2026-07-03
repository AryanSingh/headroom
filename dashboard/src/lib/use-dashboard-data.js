import { useContext } from 'react';
import { getAdminAuthHeaders } from './admin-auth';
import { getProxyUrl } from './api';
import { DashboardContext } from './dashboard-context-value';

const STANDARD_FLAG_KEYS = new Set([
  'task_aware_enabled',
  'dedup_enabled',
  'context_budget_enabled',
  'profiles_enabled',
  'shared_context_enabled',
  'cost_forecast_enabled',
  'autopilot_enabled',
  'episodic_memory_enabled',
  'audit_enabled',
]);

const LEGACY_FLAG_KEYS = new Set([
  'cache',
  'ccr',
  'memory',
  'firewall',
  'rate_limiter',
  'orchestrator',
]);

const UNSUPPORTED_STATUS_CODES = new Set([404, 405, 501, 503]);

function createDashboardError(path, message, status = null) {
  const error = new Error(message);
  error.path = path;
  error.status = status;
  return error;
}

export function useDashboardData() {
  const value = useContext(DashboardContext);
  if (!value) {
    throw new Error('useDashboardData must be used inside DashboardDataProvider');
  }
  return value;
}

export function isUnsupportedDashboardEndpointError(error) {
  if (!error) {
    return false;
  }
  if (UNSUPPORTED_STATUS_CODES.has(Number(error.status))) {
    return true;
  }
  const message = error?.message || String(error);
  return (
    message.includes('returned 404') ||
    message.includes('returned 405') ||
    message.includes('returned 501') ||
    message.includes('returned 503') ||
    message.includes('non-JSON response')
  );
}

export async function fetchDashboardJson(path) {
  const response = await fetch(getProxyUrl(path), {
    headers: getAdminAuthHeaders(),
    cache: 'no-store',
  });

  if (!response.ok) {
    throw createDashboardError(path, `${path} returned ${response.status}`, response.status);
  }

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw createDashboardError(
      path,
      `${path} returned non-JSON response`,
      response.status,
    );
  }

  return response.json();
}

export async function fetchDashboardJsonWithFallback(paths) {
  let lastError = null;

  for (const path of paths) {
    try {
      return await fetchDashboardJson(path);
    } catch (error) {
      lastError = error;
      if (!isUnsupportedDashboardEndpointError(error)) {
        throw error;
      }
    }
  }

  throw lastError || new Error(`No working endpoint found for: ${paths.join(', ')}`);
}

function chooseConfigEndpoints(updates) {
  const keys = Object.keys(updates);
  if (keys.length === 0) {
    return ['/config/flags', '/admin/config/flags'];
  }
  if (keys.every((key) => STANDARD_FLAG_KEYS.has(key))) {
    return ['/config/flags', '/admin/config/flags'];
  }
  if (keys.every((key) => LEGACY_FLAG_KEYS.has(key))) {
    return ['/admin/config/flags', '/config/flags'];
  }
  return ['/config/flags', '/admin/config/flags'];
}

export async function patchDashboardConfig(updates) {
  const candidatePaths = chooseConfigEndpoints(updates);
  let lastError = null;

  for (const path of candidatePaths) {
    const response = await fetch(getProxyUrl(path), {
      method: 'POST',
      headers: {
        ...getAdminAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      const unknownKeys = Object.keys(data?.unknown || {});
      const requestedKeys = Object.keys(updates);
      if (unknownKeys.length > 0 && unknownKeys.length === requestedKeys.length) {
        lastError = new Error(`Unsupported config update at ${path}: ${unknownKeys.join(', ')}`);
        continue;
      }
      return data || {};
    }

    lastError = createDashboardError(path, `Failed update config: ${response.status}`, response.status);
    if (!isUnsupportedDashboardEndpointError(lastError)) {
      throw lastError;
    }
  }

  throw lastError || new Error('Failed update config');
}
