---
id: EX-CH03-CLI-CONTRACT
kind: worked-example
chapter: CH-03
standards: [NIST-SSDF-1.1]
preconditions: [POSIX shell, temporary home directory, no network access]
placement: engineering-handbook/examples/cli-contract
dependencies: [bash]
invocation: bash ./atlasctl deploy --format json --profile staging
expected_output: "JSON object with command deploy status, profile staging, status ready; exit code 0."
failure_output: "ATLAS_TOKEN is required for production; exit code 77."
interpretation: The fixture separates JSON stdout from an actionable protected-profile failure on stderr.
remediation: Add explicit profile/token validation and regression tests if output or exit behavior changes.
cleanup: Remove temporary HOME and do not persist tokens or generated output.
---

# Atlas Deploy CLI contract fixture

Run the fixture without network access:

```shell
bash ./atlasctl deploy --format json --profile staging
ATLAS_PROFILE=production bash ./atlasctl deploy --format json; test $? -eq 77
```

The command is intentionally small so it can be used as a reusable contract
test specimen. It never prompts, never opens a browser, and never reads a real
credential store.
