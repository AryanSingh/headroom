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

## Executable fixture

Run the deterministic contract runner with the handbook example runner
(`python3 automation/check_examples.py engineering-handbook`) or directly from
this directory:

```shell
python3 run_cli_fixture.py
```

The runner invokes the committed `./atlasctl` twice: once for the documented
success path (`deploy --format json --profile staging`, exit 0) and once for
the protected-profile failure path (`ATLAS_PROFILE=production` without
`ATLAS_TOKEN`, exit 77). Expected output on stdout, exactly:

```text
CLI_CONTRACT_FIXTURE_PASS success-json protected-profile-blocked exit-0-exit-77
```

The wrapper is standard-library Python, sets its own `PATH` and `ATLAS_PROFILE`,
and strips any inherited `ATLAS_TOKEN` so the protected-profile path is
deterministic and offline. Failure interpretation: a non-zero exit means the
success path stopped returning clean JSON, the production path stopped blocking
at exit 77, or an error leaked onto stdout. Cleanup: the fixture writes no files
and persists no tokens, so no cleanup step is required.
