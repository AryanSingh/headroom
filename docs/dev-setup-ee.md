# Headroom Enterprise Edition (EE) Dev Setup

This guide details the bring-up process for the `headroom_ee` commercial package.

## 1. Install dependencies

The OSS package builds via `maturin`, while `headroom_ee` is a `uv` workspace member.
To sync all dependencies including the commercial extra:

```bash
uv sync --extra ee
```

## 2. Build the Rust core into the virtual environment

To build `headroom._core` into the venv so it is importable:

```bash
maturin develop --profile dev
```

## 3. Verify the setup

Run a quick test to ensure the Python imports work and the proxy compiles:

```bash
pytest tests/test_cli/test_license_cli.py -q
cargo test -p headroom-proxy
```

Note: `headroom_ee` is importable in dev because the OSS package uses `python-source = "."`. `pytest pythonpath="."` covers CI.
