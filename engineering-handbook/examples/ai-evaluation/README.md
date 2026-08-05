---
id: EX-CH17-AI-EVALUATION-README
kind: worked-example
chapter: CH-17
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025]
preconditions: [isolated Product Atlas fixture, versioned case set, approved quality and safety rubric]
placement: engineering-handbook/examples/ai-evaluation
dependencies: [Python 3 standard library]
invocation: Run python3 evaluate_fixture.py from this directory or the handbook example runner from the handbook root.
expected_output: The fixture approves only when each expected outcome, route, and safety decision matches the versioned case set.
failure_output: Any quality mismatch, wrong route, or unsafe allow decision blocks the release decision.
interpretation: The fixture proves evaluation mechanics, not real-world model quality; production release requires representative governed evidence.
remediation: Correct the policy, prompt, model configuration, evaluator, or expected contract; add a regression case and rerun the complete suite.
cleanup: The fixture reads local JSON and optionally writes a local report; it contacts no network, service, credential store, or customer system.
---

# Product Atlas offline AI quality and route-policy evaluation

Atlas evaluates three billing-support cases: an ordinary invoice-status request, a high-impact account closure, and a prompt-injection attempt. The fixture uses deterministic local rules so its evidence is reproducible without a provider credential or paid API call.

Run `python3 evaluate_fixture.py`. A passing result is:

```text
AI_EVALUATION_FIXTURE_PASS quality=1.00 route=1.00 safety=1.00 release=approved
```

The expected evidence distinguishes answer contract, selected route, and safety disposition. In a release evaluation, attach the real model/prompt/policy versions, dataset provenance, sampled human adjudications, route trace, and the release decision to this same record shape.
