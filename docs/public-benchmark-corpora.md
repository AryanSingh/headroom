# Public Benchmark Corpus Policy

Release benchmark artifacts may include only fixtures with a redistributable
source and documented provenance.

| Category | Allowed sources | Current local arm |
|---|---|---|
| Code/tool output | Repository-owned fixtures or permissively licensed public datasets | `CodeSamples`, `ToolOutputSamples` |
| RAG | Publicly redistributable retrieval/QA corpora | `RAGSamples` |
| Agent traces | Synthetic or consented, fully redacted traces | `MixedAgentTraces` |
| Verbatim preservation | Repository-owned error/path/line fixtures | `VerbatimCompactionSamples` |
| Provider-backed QA | Redistributable public QA corpora with versioned splits | SQuAD v2, HotpotQA |
| Code | Redistributable public code corpora and executable tests | CodeSearchNet, HumanEval |
| Long context | Redistributable long-context corpora | LongBench/Qasper |
| Tool use | Public schemas and executable/structural validators | BFCL only after schema validation |

Customer prompts, responses, API keys, repository contents, and identifiable
telemetry must never enter this corpus. Public reports include fixture hashes
from `benchmark-release-manifest.json` so a release can be reproduced without
disclosing fixture bodies.

For subscription-CLI studies, retain only redacted derived outputs and scores.
Never commit a provider session, authenticated CLI configuration, customer
prompt, or raw model transcript.
