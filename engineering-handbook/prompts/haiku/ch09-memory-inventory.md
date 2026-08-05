---
id: PROMPT-CH09-HAIKU-01
kind: prompt
chapter: CH-09
model_family: haiku
workload_type: memory inventory normalization
objective: Convert supplied memory records into a compact governance inventory with explicit missing evidence.
inputs: [memory source list, store topology, classification notes, retention schedule, owner list]
boundaries: [normalize supplied records only, do not infer purpose, consent, or deletion capability]
evidence: [preserve source references, layer names, classification labels, and owners in every row]
output_schema: {type: memory-inventory, fields: [memory_types, layers, purposes, retention_rules, owners, evidence_gaps]}
uncertainty: Use unknown for absent classification, retention, owner, access rule, or deletion path.
stop_conditions: [missing source list, topology cannot be connected to a memory type]
escalation: Send records without purpose, owner, or retention to the memory owner.
---

# Haiku memory inventory prompt

Create one compact row per supplied memory type. Preserve source, derivative layers, purpose, classification, retention, owner, and evidence gap. Do not treat an embedding, cache, or summary as outside governance merely because it is derived.
