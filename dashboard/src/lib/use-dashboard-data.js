import { useContext } from 'react';
import { getAdminAuthHeaders } from './admin-auth';
import { getProxyUrl } from './api';
import { DashboardContext } from './dashboard-context-value';

export function useDashboardData() {
  const value = useContext(DashboardContext);
  if (!value) {
    throw new Error('useDashboardData must be used inside DashboardDataProvider');
  }
  return value;
}

export async function fetchDashboardJson(path) {
  const response = await fetch(getProxyUrl(path), {
    headers: getAdminAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }

  return response.json();
}

export async function patchDashboardConfig(updates) {
  const response = await fetch(getProxyUrl('/admin/config/flags'), {
    method: 'POST',
    headers: {
      ...getAdminAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    throw new Error(`Failed to update config: ${response.status}`);
  }

  return response.json();
}

