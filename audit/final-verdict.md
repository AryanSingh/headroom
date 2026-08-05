# First Paid Pilot Final Verdict

**Date:** 2026-07-22  
**Candidate:** `b88669e3a19db4b42b2a71a15edf91c3725f67d5`  
**Evidence:** `audit/pilot-verification.json`

## Launch recommendation

**Decision: Conditional Go**

The software release gate is Go for the supported assisted-pilot lane. All 13
required automated checks pass, with zero failures and zero skips. The paid
launch remains conditional because the release owner and customer have not
completed the external agreement, payment, named-support, live-provider, and
customer-cluster recovery sign-offs.

| Dimension | Score | Verdict |
| --- | ---: | --- |
| Feature completeness | 92/100 | Supported client, provider, deployment, licensing, and operations paths are implemented and tested. |
| Security | 94/100 | No open Critical or High supported-path finding; external penetration testing remains outside this pass. |
| Production readiness | 90/100 | Automated release, deployment, native, dashboard, and recovery contracts pass; customer infrastructure drills remain open. |
| Product readiness | 88/100 | Assisted onboarding and support materials exist; human commercial sign-offs remain open. |

## Supported pilot matrix

- Providers: OpenAI and Anthropic.
- Clients: Codex, Claude Code, Claude Desktop MCP gateway, and compatible SDKs.
- Workstations: macOS and Linux.
- Deployments: local loopback, customer-managed Docker, and customer-managed
  Kubernetes or Helm.
- Commercial flow: manual payment confirmation and manual license issuance.
- Support model: assisted onboarding with a named direct support owner.

Claude Desktop hosted model traffic does not pass through the Cutctx proxy. The
pilot supports Claude Desktop through MCP registration and the MCP tool-output
gateway.

## Automated evidence

The required automated checks pass:

1. Pilot document contracts.
2. Network and deployment security, 40 tests.
3. License and SQLite durability, 46 tests.
4. Supported provider and client paths, 215 tests.
5. Python lint for changed release files.
6. Dashboard unit tests, 13 tests.
7. Dashboard production build.
8. Rust formatting.
9. Rust workspace tests.
10. Version alignment at 0.31.0.
11. Commercial SPDX and package-boundary check.
12. Helm rendering with distinct network credentials.
13. Docker Compose validation with private state services and persistent
    Cutctx state.

The Python release clusters pass 304 tests. The machine-readable report records
the command, return code, and output tail for each check.

## Closed Critical and High findings

- Non-loopback provider HTTP and WebSocket routes fail closed without a
  provider-route credential.
- Compose and Helm require distinct admin, provider-route, and agent-client
  credentials.
- Helm rejects missing or reused credentials before deployment.
- Root Compose no longer publishes Qdrant or Neo4j host ports, requires an
  explicit Neo4j password, and persists `/home/nonroot/.cutctx`.
- Cross-connection tests prove bounded SQLite lock waiting for request metrics
  and license activation.
- The pilot has onboarding, acceptance, support, incident, backup, restore,
  upgrade, rollback, license/billing, and limitation documents.
- Every commercial Python file passes the SPDX boundary scan.
- The dashboard unit contract matches the current overview layout and the
  production dashboard build passes.

## Required external sign-offs

The release owner must close each item before giving the customer paid access:

- contracting entity and approved pilot agreement;
- legal review of terms, privacy terms, and any required DPA;
- payment or invoice confirmation;
- named support owner and written response target;
- customer approval of data handling and telemetry settings;
- live OpenAI and Anthropic acceptance in the customer environment;
- customer-cluster backup restore and rollback drill;
- production change window and rollback owner.

These items require people, customer credentials, and customer infrastructure.
The repository cannot close them.

## Open Medium and Low risks

| Risk | Severity | Pilot control |
| --- | --- | --- |
| No external penetration test in this pass | Medium | Keep the deployment private, terminate TLS, use distinct secrets, and schedule third-party testing before a broader release. |
| Live provider behavior was not exercised with customer credentials | Medium | Run `docs/pilot/customer-acceptance-test.md` during onboarding before production traffic. |
| Restore and rollback were not executed on the customer's cluster | Medium | Treat the documented drill as a launch sign-off. |
| Windows and non-OpenAI/Anthropic paths lack pilot certification | Low for this contract | Keep them outside the order form and known-limitations statement. |
| Whole-product accessibility and broad SDK coverage remain below a GA bar | Low for the supported operator-assisted pilot | Keep the dashboard operator-only and limit the commitment to the tested clients. |

## Release decision rule

- Release the candidate to the pilot after every external sign-off is recorded.
- Keep the decision at Conditional Go while any external sign-off remains open.
- Change the decision to No-Go if the customer acceptance test reveals a
  Critical or High issue, a restore drill fails, or the release artifact differs
  from candidate `b88669e3a19db4b42b2a71a15edf91c3725f67d5`.
