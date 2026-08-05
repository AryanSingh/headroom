---
id: TMPL-INCIDENT-REVIEW-001
kind: template
title: Incident Review
field_instructions:
  timeline: Use dated facts and distinguish observations from hypotheses.
  contributing_factors: Describe conditions that increased likelihood or impact.
  actions: Give owner, due date, and effectiveness check for each action.
completed_example:
  timeline: Atlas pricing refresh lag began 09:14 UTC and recovered 10:02 UTC on 2026-07-18.
  contributing_factors: A queue limit and missing alert delayed operator awareness.
  actions: SRE Elena adds queue-depth alert by 2026-07-25 and tests it in a game day.
---

# Incident Review

## Field instructions

| Field | How to complete it |
| --- | --- |
| Summary | State customer effect, duration, and service scope. |
| Timeline | List timestamped events, decisions, and evidence sources. |
| Contributing factors | Describe technical and process conditions without assigning blame. |
| Response assessment | Record what helped, what delayed response, and communication quality. |
| Actions | Name accountable owner, due date, and effectiveness measure. |

## Completed example: Product Atlas

**Incident:** INC-ATLAS-2026-031, delayed pricing refresh.  
**Customer effect:** 18 enterprise tenants saw inventory recommendations up to 48 minutes old from 09:14 to 10:02 UTC on 2026-07-18.  
**Timeline:** At 09:14 the queue reached its configured limit. At 09:29 support reported stale recommendations. At 09:37 Elena, Incident Commander, paused the batch import. At 10:02 the backlog cleared.  
**Contributing factors:** Queue capacity matched average traffic, and no queue-depth alert paged the on-call engineer.  
**Actions:** Elena Chen adds a queue-depth alert by 2026-07-25 and validates it in a game day; Engineering Manager Ravi Shah reviews capacity assumptions by 2026-08-01.
