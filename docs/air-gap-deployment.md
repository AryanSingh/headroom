# Air-Gap Deployment Guide

CutCtx supports fully offline deployment. This guide covers all required
steps to run CutCtx in an environment with no internet access.

## Pre-requisites

All dependencies must be downloaded on an internet-connected machine first.
The following must be pre-staged:

### 1. Python package bundle

```bash
# On internet-connected machine:
pip download "headroom-ai[all]" -d cutctx-bundle/
tar czf cutctx-bundle.tar.gz cutctx-bundle/
# Transfer cutctx-bundle.tar.gz to air-gapped environment

# On air-gapped machine:
tar xzf cutctx-bundle.tar.gz
pip install --no-index --find-links cutctx-bundle/ "headroom-ai[all]"
```

### 2. HuggingFace models (ONNX)

```bash
# On internet-connected machine:
python - << 'EOF'
from huggingface_hub import snapshot_download
# Kompress compression model
snapshot_download("chopratejas/kompress-v2-base",
                  local_dir="hf-cache/kompress-v2-base")
EOF
tar czf hf-cache.tar.gz hf-cache/

# On air-gapped machine:
tar xzf hf-cache.tar.gz
export HF_HUB_OFFLINE=1
export TRANSFORMERS_CACHE=/path/to/hf-cache
```

### 3. Docker image (if using Docker deployment)

```bash
# On internet-connected machine:
docker pull ghcr.io/aryansingh/cutctx:latest
docker save ghcr.io/aryansingh/cutctx:latest | gzip > cutctx-image.tar.gz

# On air-gapped machine:
docker load < cutctx-image.tar.gz
```

## Offline License Validation

In air-gap mode, the proxy cannot phone home to validate licenses.
Set the following environment variables:

```bash
export CUTCTX_LICENSE_KEY="ent-your-key-here"
export HEADROOM_OFFLINE_MODE=1
export HEADROOM_LICENSE_HMAC_SECRET="your-shared-secret"
```

The HMAC secret must be pre-shared by the CutCtx team during onboarding.
The license key contains an embedded HMAC signature that the proxy verifies
locally without a network call.

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `HF_HUB_OFFLINE` | Yes | Set to `1` to disable HuggingFace downloads |
| `TRANSFORMERS_CACHE` | Yes | Path to pre-staged model cache |
| `ORT_STRATEGY` | Recommended | Set to `system` to use system ONNX Runtime |
| `HEADROOM_OFFLINE_MODE` | Yes | Disables all external HTTP calls |
| `HEADROOM_LICENSE_HMAC_SECRET` | Yes | Pre-shared key for offline license validation |
| `HEADROOM_ADMIN_API_KEY` | Yes | Admin authentication key |

## Validation Checklist

After deployment, verify:

```bash
# 1. Proxy starts without network calls
lsof -i | grep cutctx  # should only show localhost:8787

# 2. Compression works offline
curl http://localhost:8787/v1/compress \
  -H "Content-Type: application/json" \
  -d '{"content": "test compression in air-gap mode"}'

# 3. License validates locally
cutctx license status
# Should show: "License valid (offline mode)"
```

## Troubleshooting

### Model not found errors

Ensure `TRANSFORMERS_CACHE` points to the directory containing the
pre-staged model files. The directory structure should be:

```
/path/to/hf-cache/
  kompress-v2-base/
    config.json
    tokenizer.json
    model.onnx
```

### License validation fails

1. Verify `HEADROOM_LICENSE_HMAC_SECRET` matches the secret used
   during license generation
2. Check the license key format: `{tier}-{random_id}-{hmac_signature}`
3. Run `cutctx license status --verbose` for detailed diagnostics

### No outbound connections

In truly air-gapped environments, verify DNS is not resolving external
hostnames:

```bash
# Check for DNS leaks
strace -f -e trace=network cutctx proxy --port 8787 2>&1 | grep connect
# Should only show connections to localhost
```
