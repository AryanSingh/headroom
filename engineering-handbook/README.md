# Enterprise Engineering Manual source

This directory is the canonical, source-only edition of the Enterprise
Engineering Manual. `SUMMARY.md` defines publication order and is also the
coverage manifest used by the validator. Generated Markdown, DOCX, PDF, CSV,
prompt exports, checksums, and visual-QA artifacts belong under the ignored
`dist/` tree or in CI/release artifacts.

## Foundation contract

- [Publication manifest](SUMMARY.md)
- [Handbook metadata](metadata.yaml)
- [Control schema](governance/control-schema.md)
- [KPI schema](governance/kpi-schema.md)
- [Standards registry](standards/README.md)
- [Prompt schema](prompts/schema.md)
- [Prompt selection guide](prompts/prompt-selection-guide.md)

## Validate the source

Install the exact automation dependencies into an isolated environment, then
run the validator with the pinned workspace Python runtime:

```bash
/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pip install --requirement engineering-handbook/automation/requirements.lock

/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  engineering-handbook/automation/validate_handbook.py engineering-handbook
```

Use `--format json` for machine-readable findings. Exit status `0` means clean,
`1` means blocking findings, `2` means warnings only, and `3` means execution or
configuration failure.

## Check executable examples

Example packages declare their command, timeout, fixtures, expected output,
cleanup, dependency assumptions, and offline/network policy in `example.yaml`.
Run all discovered packages with:

```bash
/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  engineering-handbook/automation/check_examples.py engineering-handbook
```

The runner copies each package into a temporary directory, blocks credential-like
environment values and mutable network commands, captures process results, and
runs declared cleanup even after timeout or failure.

## Build the publication spike

DOCX is the layout authority and PDF is derived from it with pinned headless
LibreOffice. The first required render gate is the focused publication spike:

```bash
/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  engineering-handbook/automation/build_handbook.py engineering-handbook dist --pilot
```

This creates ignored local DOCX, PDF, and page PNGs. Inspect every page recorded
in `dist/visual-qa/pilot-ledger.json` before changing the frozen publication
style at `build/styles/publication.yaml`. The committed
`build/artifact-manifest.yaml` lists release outputs and their checksum roles;
`build/styles/reference.docx` is generated deterministically by the same builder.

## Authoring rule

Canonical Markdown uses YAML front matter for typed assets and ordinary
Markdown for structure. Raw HTML is unsupported. Local links, heading anchors,
images, standards references, prompt metadata, catalog IDs, and required asset
fields are checked offline before publication.
