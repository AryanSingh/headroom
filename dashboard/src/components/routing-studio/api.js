import { getAdminAuthHeaders } from "../../lib/admin-auth";
import { getProxyUrl } from "../../lib/api";

export async function routingStudioApi(path, options = {}) {
  const response = await fetch(getProxyUrl(`/v1/orchestration${path}`), {
    cache: "no-store",
    ...options,
    headers: {
      ...getAdminAuthHeaders(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload?.detail?.message || payload?.detail || response.status;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return payload;
}

export const listContracts = () => routingStudioApi("/contracts");

export const saveDraft = (contract, expectedRevision) =>
  routingStudioApi(`/contracts/${contract.id}/draft`, {
    method: "PUT",
    body: JSON.stringify({ contract, expected_revision: expectedRevision }),
  });

export const simulateDraft = (contract, scenario) =>
  routingStudioApi(`/contracts/${contract.id}/simulate`, {
    method: "POST",
    body: JSON.stringify({ contract, scenario }),
  });

export const getContractEvidence = (contract) =>
  routingStudioApi(
    `/contracts/${contract.id}/versions/${contract.version}/evidence`,
  );

export const shadowContract = (contract) =>
  routingStudioApi(
    `/contracts/${contract.id}/versions/${contract.version}/shadow`,
    { method: "POST" },
  );

export const promoteContract = (contract) =>
  routingStudioApi(
    `/contracts/${contract.id}/versions/${contract.version}/promote`,
    { method: "POST" },
  );

export const pauseContract = (contract) =>
  routingStudioApi(
    `/contracts/${contract.id}/versions/${contract.version}/pause`,
    { method: "POST" },
  );

export const rollbackContract = (contract) =>
  routingStudioApi(
    `/contracts/${contract.id}/versions/${contract.version}/rollback`,
    { method: "POST" },
  );
