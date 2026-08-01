import { CircleAlert, Gauge, ShieldCheck } from "lucide-react";

export function getOrchestratorRecommendation({
  configAvailable,
  roleCount,
  mode,
  evidenceStatus,
  providers,
}) {
  if (!configAvailable) {
    return { icon: CircleAlert, label: "Update the proxy", detail: "Runtime controls need a compatible proxy build.", target: null };
  }
  if (providers.some((provider) => provider.healthy === false)) {
    return { icon: CircleAlert, label: "Check provider health", detail: "A configured compatibility provider is disabled.", target: "configuration" };
  }
  if (mode === "off" && roleCount === 0) {
    return { icon: Gauge, label: "Set up role assignments", detail: "Lock important workloads to approved models before enabling routing.", target: "configuration" };
  }
  if (evidenceStatus === "ready") {
    return { icon: ShieldCheck, label: "Review rollout gates", detail: "Measured evidence is ready for a contract rollout decision.", target: "contracts" };
  }
  if (evidenceStatus === "collecting") {
    return { icon: Gauge, label: "Continue collecting evidence", detail: "Shadow samples are still building the quality-safe routing frontier.", target: null };
  }
  if (mode === "off") {
    return { icon: Gauge, label: "Start with Auto routing", detail: "Auto keeps uncertain work on the requested model.", target: null };
  }
  return { icon: ShieldCheck, label: "Routing is operational", detail: "Current routing and safety signals do not require action.", target: null };
}
