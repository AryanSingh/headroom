# Prompt record schema

Each chapter provides one Opus, one Sonnet, and one Haiku prompt as standalone
files or uniquely anchored records. The three prompts address different
workloads and produce different output declarations; changing only the model
family is invalid.

## Required metadata

| Field | Contract |
| --- | --- |
| `id` | Globally unique stable prompt ID. |
| `kind` | Literal value `prompt`. |
| `chapter` | Stable chapter ID served by the prompt. |
| `model_family` | `opus`, `sonnet`, or `haiku`. |
| `workload_type` | Distinct workload suited to the selected family. |
| `objective` | Decision or artifact the prompt helps produce. |
| `inputs` | Required evidence and caller-provided context. |
| `boundaries` | Files, systems, time range, authority, and excluded scope. |
| `evidence` | Evidence standards and citation expectations. |
| `output_schema` | Required fields, ordering, and machine-readable shape where relevant. |
| `uncertainty` | How unknown, inferred, and conflicting claims are represented. |
| `stop_conditions` | Conditions that prevent a trustworthy result. |
| `escalation` | Role or workflow receiving blocked or high-risk cases. |

## Front matter example

```yaml
id: PROMPT-CH01-SONNET-01
kind: prompt
chapter: CH-01
model_family: sonnet
workload_type: focused evidence review
objective: Reproduce and classify a reported engineering finding
inputs:
  - finding statement
  - relevant source files
  - verification command
boundaries:
  - inspect only the supplied repository paths
  - do not mutate external systems
evidence:
  - cite file paths and command output
output_schema:
  type: object
  required: [status, evidence, severity, remediation]
uncertainty: Separate observed facts, inferences, and unresolved questions.
stop_conditions:
  - required evidence is unavailable
  - reproduction would require production credentials
escalation: Return the blocked evidence request to the chapter owner.
```

## Prompt body

After front matter, state the role, task sequence, evidence rules, output
contract, and safety constraints in direct language. Prompt bodies may include
parameter markers documented by the prompt itself; undocumented drafting
markers are rejected by validation.
