---
id: TMPL-THREAT-MODEL-001
kind: template
title: Threat Model
field_instructions:
  system_scope: Define boundaries, assets, actors, and trust crossings.
  threats: Describe abuse case, impact, existing measures, and treatment decision.
  review_trigger: State when the model will be revisited.
completed_example:
  system_scope: Atlas Inventory API handles tenant inventory updates from authenticated warehouse connectors.
  threats: Connector token replay could alter inventory; short-lived tokens and nonce checks reduce risk.
  review_trigger: Review before connector-auth changes, new regions, or a relevant security incident.
---

# Threat Model

## Field instructions

| Field | How to complete it |
| --- | --- |
| System boundary | Identify assets, actors, data flows, and trust boundaries. |
| Threat scenarios | State the abuse case, precondition, impact, and affected asset. |
| Existing measures | Record controls that reduce likelihood or impact. |
| Treatment | Choose mitigation, acceptance, transfer, or avoidance and name owner. |
| Review trigger | State a design, release, or incident event that causes review. |

## Completed example: Product Atlas

**System boundary:** Atlas Inventory API accepts authenticated inventory updates from warehouse connectors and writes tenant inventory records. Warehouse connectors cross an internet-facing API boundary; the API crosses into the tenant data store.  
**Threat scenario:** A stolen connector token could replay an inventory update. The effect could include incorrect availability recommendations for one tenant.  
**Existing measures:** Atlas uses short-lived connector tokens, request nonces, tenant-scoped authorization, and audit logs.  
**Treatment:** Security Lead Leena Shah owns a mitigation to alert on repeated nonce failures by 2026-08-20.  
**Review trigger:** Revisit before an authentication protocol change, deployment to a new region, or a connector security incident.
