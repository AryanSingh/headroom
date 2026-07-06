import { useCallback, useEffect, useMemo, useState } from 'react';
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
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(null);

  const load = useCallback(async () => {
    try {
      const [statsData, healthData] = await Promise.all([
        fetchDashboardJson('/stats?cached=1'),
        fetchDashboardJson('/health'),
      ]);

      setStats(statsData);
      setHealth(healthData);
      setError(null);
      setLastUpdated(new Date().toISOString());

      // Optional control-plane flags should not be treated like a broken
      // dashboard when the running proxy simply does not expose that surface.
      if (statsData?.config != null) {
        try {
          const flags = await fetchDashboardJsonWithFallback([
            '/config/flags',
            '/admin/config/flags',
          ]);
          setConfigFlags(flags);
          setConfigFlagsError(null);
        } catch (loadError) {
          if (isUnsupportedDashboardEndpointError(loadError)) {
            setConfigFlags(null);
            setConfigFlagsError(null);
          } else {
            setConfigFlags(null);
            setConfigFlagsError(loadError.message || String(loadError));
          }
        }
      } else {
        setConfigFlags(null);
        setConfigFlagsError(null);
      }
    } catch (loadError) {
      setError(loadError.message || String(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

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
    setLoading(true);
    await Promise.all([load(), loadHistory()]);
  }, [load, loadHistory]);

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
      await Promise.all([load(), loadHistory()]);
    };

    run();
    const statsId = setInterval(() => {
      if (!cancelled) {
        load();
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
  }, [load, loadHistory]);

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
      error,
      lastUpdated,
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
      error,
      lastUpdated,
      refresh,
    ],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}
