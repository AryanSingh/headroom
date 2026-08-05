# Publication Spike

This fixture proves the source-to-DOCX-to-PDF path before long-form chapter
authoring. Run it with the pinned runtime:

```shell
/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 engineering-handbook/automation/build_handbook.py engineering-handbook dist --pilot
```

Inspect every PNG named in `dist/visual-qa/pilot-ledger.json`. The generated
files are local QA artifacts and are intentionally not committed.
