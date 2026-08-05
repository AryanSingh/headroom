---
id: KPI-CATALOG-CLI
kind: kpi-catalog
chapter: CH-03
kpis:
  - id: KPI-CLI-001
    name: Non-interactive command success rate
    decision: Whether automated workflows can safely rely on the CLI.
    calculation: successful bounded non-interactive contract cases divided by all required non-interactive contract cases per release.
    source: CLI contract test report
    frequency: each release
    owner: CLI owner
    target: 100 percent
    warning: below 100 percent
    distortions: [excluding unsupported commands, treating a timeout as a pass]
    anti_gaming: [inventory commands from help and automation repositories, count timeouts as failures]
    interpretation: A single CI-hanging mutating command blocks release even when the rate rounds to 99 percent.
---

# CLI KPI catalog

Product Atlas treats automation safety as a gate, not a rounded trend line.
