# Risk Severity Model

## Severity model

Estimate impact and likelihood using current evidence. The resulting severity guides attention and escalation; it does not replace informed judgment.

| Severity | Impact and likelihood signal | Initial handling target | Decision owner |
| --- | --- | --- | --- |
| Critical | material harm, broad compromise, or prolonged core-service loss is credible | convene response leadership now | executive incident delegate |
| High | significant customer, security, financial, or compliance exposure is credible | assign owner and containment plan in one business day | service owner with domain lead |
| Medium | bounded harm or a recoverable control gap is credible | plan remediation in the next delivery cycle | engineering manager |
| Low | limited impact with compensating controls | track and review at normal cadence | product or service owner |

## Assessment factors

Assess affected users, data sensitivity, exploitability, reversibility, regulatory or contractual exposure, operational blast radius, and confidence in the available evidence. Record the factor that drove the rating.

## Product Atlas example

Atlas found that a staging export job could include tenant names in an internal error log. The Security Lead rated it Medium: the log stayed inside a restricted environment, but the data classification and broad viewer group increased exposure. The team narrowed access that week and added a redaction test to the following release.

## Reassessment triggers

Reassess after new evidence, changed scope, failed mitigation, wider customer impact, or a related incident. Keep the original rating and rationale in the record so reviewers can see why the assessment changed.
