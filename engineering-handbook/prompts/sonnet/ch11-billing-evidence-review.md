---
id: PROMPT-CH11-SONNET-01
kind: prompt
chapter: CH-11
model_family: sonnet
workload_type: focused billing reconciliation evidence review
objective: Determine whether one account-period reconciliation is supported by traceable usage, invoice, credit, and approval evidence.
inputs: [account identifier, period, usage events, aggregation result, invoice lines, credits, approvals, support record]
boundaries: [review one account-period only, use supplied evidence only, do not calculate unstated tax or approve refunds]
evidence: [cite each usage event ID, aggregation record, invoice reference, credit approval, reconciliation tolerance, and source owner]
output_schema: {type: billing-evidence-review, fields: [verdict, ledger-chain, discrepancies, evidence-gaps, required-follow-up]}
uncertainty: Mark absent event identity, unapproved credit, or unmatched invoice line as unresolved.
stop_conditions: [missing account-period, absent usage ledger, unavailable invoice, no stated tolerance]
escalation: Send an unexplained customer charge, duplicate event, or missing adjustment approval to the billing owner.
---

# Sonnet billing evidence review prompt

Review one account-period from accepted usage to customer-visible invoice. Confirm event idempotency, aggregation linkage, approved adjustments, and stated reconciliation tolerance. List only the smallest missing record or fixture needed to turn each discrepancy into a decision.
