import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchDashboardJson,
  fetchDashboardJsonWithFallback,
  isUnsupportedDashboardEndpointError,
} from './use-dashboard-data';
import { adoptAdminKeyFromUrl } from './admin-auth';
import { DashboardContext } from './dashboard-context-value';

export function DashboardDataProvider({ children }) {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [configFlags, setConfigFlags] = useState(null);
  const [configFlagsError, setConfigFlagsError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [refreshError, setRefreshError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [committedGeneration, setCommittedGeneration] = useState(0);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(null);
  const currentGeneration = useRef(0);
  const latestExplicitRefresh = useRef(0);

  const loadConfigFlags = useCallback(async (statsData, generation) => {
    if (statsData?.config == null) {
      if (generation === currentGeneration.current) {
        setConfigFlags(null);
        setConfigFlagsError(null);
      }
      return;
    }

    try {
      const flags = await fetchDashboardJsonWithFallback([
        '/config/flags',
        '/admin/config/flags',
      ]);
      if (generation === currentGeneration.current) {
        setConfigFlags(flags);
        setConfigFlagsError(null);
      }
    } catch (loadError) {
      if (generation !== currentGeneration.current) {
        return;
      }
      if (isUnsupportedDashboardEndpointError(loadError)) {
        setConfigFlags(null);
        setConfigFlagsError(null);
      } else {
        setConfigFlags(null);
        setConfigFlagsError(loadError.message || String(loadError));
      }
    }
  }, []);

  const loadCurrent = useCallback(async ({ initial = false, explicit = false } = {}) => {
    const generation = ++currentGeneration.current;
    if (explicit) {
      latestExplicitRefresh.current = generation;
      setRefreshing(true);
    }
    try {
      const [statsData, healthData] = await Promise.all([
        fetchDashboardJson('/stats?cached=1'),
        fetchDashboardJson('/health'),
      ]);

      if (generation !== currentGeneration.current) {
        return { ok: false, stale: true, generation };
      }

      setStats(statsData);
      setHealth(healthData);
      setError(null);
      setRefreshError(null);
      setLastUpdated(new Date().toISOString());
      setCommittedGeneration(generation);
      // A newer polling snapshot can supersede the initial request. Any
      // committed snapshot is sufficient to leave the initial loading shell.
      setLoading(false);

      // Optional flags are also independent: they cannot delay the stats
      // result used to confirm a mode change.
      void loadConfigFlags(statsData, generation);
      return { ok: true, committed: true, generation, stats: statsData, health: healthData };
    } catch (loadError) {
      if (generation !== currentGeneration.current) {
        return { ok: false, stale: true, generation };
      }
      const message = loadError.message || String(loadError);
      if (initial) {
        setError(message);
      } else {
        setRefreshError(message);
      }
      return { ok: false, error: message, generation };
    } finally {
      if (initial && generation === currentGeneration.current) {
        setLoading(false);
      }
      if (
        generation === currentGeneration.current &&
        latestExplicitRefresh.current > 0 &&
        latestExplicitRefresh.current <= generation
      ) {
        setRefreshing(false);
        latestExplicitRefresh.current = 0;
      }
    }
  }, [loadConfigFlags]);

  const loadHistory = useCallback(async () => {
    try {
      setHistoryLoading(true);
      const data = await fetchDashboardJson('/stats-history');
      setHistoryData(data);
      setHistoryError(null);
    } catch (loadError) {
      setHistoryError(loadError.message || String(loadError));
      setHistoryData(null);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    const current = loadCurrent({ explicit: true });
    // History is intentionally fire-and-forget: it must never delay current
    // dashboard data or a routing-mode acknowledgement.
    void loadHistory();
    return current;
  }, [loadCurrent, loadHistory]);

  useEffect(() => {
    let cancelled = false;

    // Must happen before the first fetch: a bookmarked `/dashboard?key=...`
    // link only authenticates the initial HTML page load, not any of this
    // component's own client-side requests.
    adoptAdminKeyFromUrl();

    const run = async () => {
      if (cancelled) {
        return;
      }
      void loadHistory();
      await loadCurrent({ initial: true });
    };

    run();
    const statsId = setInterval(() => {
      if (!cancelled) {
        void loadCurrent();
      }
    }, 5000);
    const historyId = setInterval(() => {
      if (!cancelled) {
        loadHistory();
      }
    }, 60000);

    return () => {
      cancelled = true;
      clearInterval(statsId);
      clearInterval(historyId);
    };
  }, [loadCurrent, loadHistory]);

  const value = useMemo(
    () => ({
      stats,
      health,
      configFlags,
      configFlagsError,
      historyData,
      historyLoading,
      historyError,
      loading,
      refreshing,
      error,
      refreshError,
      lastUpdated,
      committedGeneration,
      refresh,
    }),
    [
      stats,
      health,
      configFlags,
      configFlagsError,
      historyData,
      historyLoading,
      historyError,
      loading,
      refreshing,
      error,
      refreshError,
      lastUpdated,
      committedGeneration,
      refresh,
    ],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}
