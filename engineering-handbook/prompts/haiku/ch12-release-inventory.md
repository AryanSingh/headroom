---
id: PROMPT-CH12-HAIKU-01
kind: prompt
chapter: CH-12
model_family: haiku
workload_type: release record inventory normalization
objective: Convert supplied release records into a compact inventory of candidates, artifacts, environments, gates, rollback status, owners, and evidence gaps.
inputs: [release records, source revisions, artifact registry records, gate results, deployment events, rollback plans, owner list]
boundaries: [normalize supplied records only, do not infer compatibility, mark a release approved, or invent a digest]
evidence: [preserve release ID, source revision, artifact digest, target, gate reference, rollback reference, owner, and source reference]
output_schema: {type: release-inventory, fields: [candidates, artifacts, environments, gates, rollback-status, owners, evidence-gaps]}
uncertainty: Use unknown for an absent artifact, gate, target, rollback record, or owner.
stop_conditions: [missing release records, records cannot be associated with a candidate or target]
escalation: Send a production candidate without immutable artifact identity or rollback owner to the release owner.
---

# Haiku release inventory prompt

Create one compact row per release candidate. Preserve source, digest, environment, gate, rollback, owner, and missing evidence exactly as supplied. Do not treat a successful deployment event as proof of safe customer outcome or rollback readiness.
