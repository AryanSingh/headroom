const rejected = (result) => result.status === 'rejected';

export function resolveDashboardLoadResults(statsResult, healthResult) {
  const authenticationFailure = [statsResult, healthResult].find(
    (result) => rejected(result) && Number(result.reason?.status) === 401,
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
