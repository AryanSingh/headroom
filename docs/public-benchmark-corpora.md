# Public Benchmark Corpus Policy

Release benchmark artifacts may include only fixtures with a redistributable
source and documented provenance.

| Category | Allowed sources | Current local arm |
|---|---|---|
| Code/tool output | Repository-owned fixtures or permissively licensed public datasets | `CodeSamples`, `ToolOutputSamples` |
| RAG | Publicly redistributable retrieval/QA corpora | `RAGSamples` |
| Agent traces | Synthetic or consented, fully redacted traces | `MixedAgentTraces` |
| Verbatim preservation | Repository-owned error/path/line fixtures | `VerbatimCompactionSamples` |

Customer prompts, responses, API keys, repository contents, and identifiable
telemetry must never enter this corpus. Public reports include fixture hashes
from `benchmark-release-manifest.json` so a release can be reproduced without
disclosing fixture bodies.
