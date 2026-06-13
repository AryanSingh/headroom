# Headroom Customer Onboarding Runbook

## Goal

Get a paying customer from signed agreement to successful rollout with measurable value.

## Pre-Onboarding Checklist

- Confirm selected tier
- Confirm deployment mode
- Confirm technical owner
- Confirm security reviewer if applicable
- Confirm success metrics for the first 14 days

## Team Onboarding Flow

### Day 0
- Share install guide
- Confirm provider credentials
- Confirm proxy endpoint path

### Day 1
- Deploy proxy
- Route first requests
- Verify local dashboard and stats

### Day 3
- Review first savings report
- Tune savings profile
- Confirm team analytics visibility

### Day 7
- Review usage patterns
- Export report
- Agree on renewal or expansion indicators

## Enterprise Onboarding Flow

### Step 1
- Choose Docker, Kubernetes, Helm, or air-gap deployment

### Step 2
- Enable admin API key
- Enable SSO if required
- Verify RBAC roles

### Step 3
- Enable audit logging
- Review retention settings
- Review deployment inventory and fleet heartbeat flow if needed

### Step 4
- Provision users and groups via SCIM-style APIs if required

### Step 5
- Run security and architecture review with the customer

### Step 6
- Produce first ROI and admin operations review

## Success Milestones

- first request succeeds
- first savings report generated
- admin auth verified
- at least one report exported
- pilot owner signs off on technical fit

## Escalation Triggers

- no traffic routed by day 3
- admin auth blocked by day 5
- security review unresolved after first packet review
- no measurable value signal by day 10
