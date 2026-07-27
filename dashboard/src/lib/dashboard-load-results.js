const rejected = (result) => result.status === 'rejected';

export function isDashboardAuthenticationFailure(error) {
  const status = Number(error?.status);
  if (status === 401) {
    return true;
  }
  if (status !== 429) {
    return false;
  }
  const haystack = `${error?.message || ''} ${JSON.stringify(error?.detail || {})}`.toLowerCase();
  return (
    haystack.includes('admin authentication')
    || haystack.includes('admin credentials')
    || haystack.includes('authentication attempts')
  );
}

export function resolveDashboardLoadResults(statsResult, healthResult) {
  const authenticationFailure = [statsResult, healthResult].find(
    (result) => rejected(result) && isDashboardAuthenticationFailure(result.reason),
  );

  if (authenticationFailure) {
    throw authenticationFailure.reason;
  }
  if (rejected(statsResult)) {
    throw statsResult.reason;
  }
  if (rejected(healthResult)) {
    throw healthResult.reason;
  }

  return {
    statsData: statsResult.value,
    healthData: healthResult.value,
  };
}
