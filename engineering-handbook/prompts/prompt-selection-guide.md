# Prompt selection guide

Select the family from the work, risk, ambiguity, and expected artifact rather
than from a generic quality ranking.

| Family | Use for | Typical output |
| --- | --- | --- |
| Opus | Cross-system architecture analysis, threat modeling, ambiguous high-risk investigations, release decisions, and multi-document synthesis. | Decision memo, threat model, dependency analysis, or risk-ranked investigation. |
| Sonnet | Focused code review, test design, workflow verification, finding reproduction, evidence analysis, and remediation planning. | Reproducible findings, test plan, evidence assessment, or implementation plan. |
| Haiku | Inventories, mechanical checks, evidence normalization, checklist execution, report formatting, and regression triage. | Tables, normalized records, checklist results, or concise triage queues. |

## Escalation

Move from Haiku to Sonnet when classification requires interpretation, from
Sonnet to Opus when the decision spans systems or material risk, and from any
model to a human owner when evidence is missing, authority is insufficient, or
the declared stop conditions apply. A larger model does not remove the need for
reproducible evidence or domain review.

## Chapter requirement

Every chapter links all three prompt families. Workload and output declarations
remain substantively distinct while sharing chapter terminology, evidence
paths, severity definitions, and governance boundaries.
