# Evidence Standard

## Evidence qualities

Evidence is useful when a reviewer can identify its source, time, scope, producer, and integrity characteristics. Store the durable artifact or a stable reference to it; a status update alone rarely supports a later decision review.

| Quality | Review question | Product Atlas example |
| --- | --- | --- |
| Traceable | Can the record identify its source and owner? | CI job URL and commit `a91c2f7` |
| Time-bound | Does it state when collection occurred? | 2026-08-03 14:22 UTC |
| Scoped | Which release, service, or dataset did it cover? | Atlas API release 4.8.0 |
| Reproducible | Can another person repeat or inspect it? | versioned query and redacted fixture |
| Protected | Is access appropriate for its sensitivity? | restricted incident folder with access log |

## Collection procedure

1. Identify the decision and the claims that need support.
2. Capture the smallest durable artifact that demonstrates each claim.
3. Record source, collector, timestamp, scope, retention location, and sensitivity.
4. Check whether a reviewer can retrieve the artifact using the recorded location.
5. Record gaps as findings or exceptions instead of describing unsupported confidence.

## Retention guidance

Set retention from the product's record schedule, contractual commitments, and incident needs. Keep secrets out of general evidence stores. Use a reference to a protected location when the evidence includes customer data, credentials, exploit details, or personnel information.

## Product Atlas example

Atlas approved a pricing-engine migration after the data steward attached a row-count query, checksum comparison, rollback drill log, and release decision. The evidence register marked the query output as Internal, retained it for 18 months under Atlas's record schedule, and pointed reviewers to the restricted release folder.
