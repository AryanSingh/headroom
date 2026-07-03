# Cutctx Air-Gap Deployment Guide

For defense, healthcare, and highly-regulated environments, Cutctx supports a full offline deployment mode with zero outbound internet connectivity requirements.

## 1. Pre-fetching Machine Learning Weights

Cutctx relies on ONNX weights for the AST/semantic compression engine. To run offline, these must be bundled inside the container or mounted to a persistent volume.

1. On an internet-connected machine, download the `kompress-v2-base` model from HuggingFace:
```bash
git lfs install
git clone https://huggingface.co/cutctx/kompress-v2-base /opt/cutctx/models
```

2. Package the `/opt/cutctx/models` directory into a tarball and securely transfer it across the air-gap to the target environment.

3. Set the following environment variable to enforce offline-only model loading:
```env
HF_HUB_OFFLINE=1
CUTCTX_MODEL_CACHE_DIR=/opt/cutctx/models
```

## 2. Offline License Validation

Because an air-gapped Cutctx deployment cannot reach hosted license-validation services, you must use an offline-issued enterprise license key.

1. Generate or obtain an offline key through your commercial licensing workflow.
2. Pass the key to the Cutctx proxy via the environment:
```env
CUTCTX_EE_LICENSE_KEY="ptsk_off_..."
```
*Cutctx uses Ed25519 signature verification (`cutctx_ee/billing/license_token.py`) to cryptographically guarantee the validity of the key and its embedded seat constraints without phoning home.*

## 3. Container Images

Use the official `cutctx-proxy:latest-distroless` image. Transfer the image to your private, air-gapped container registry:

```bash
# On internet-connected machine
docker pull cutctx/proxy:latest-distroless
docker save cutctx/proxy:latest-distroless -o cutctx.tar

# Transfer cutctx.tar across the air-gap

# On air-gapped machine
docker load -i cutctx.tar
docker tag cutctx/proxy:latest-distroless private-registry.internal.corp/cutctx/proxy:latest-distroless
docker push private-registry.internal.corp/cutctx/proxy:latest-distroless
```

## 4. Telemetry Disable

OpenTelemetry and external metrics collection should be disabled or routed to an internal sink:
```env
CUTCTX_OTEL_EXPORT_ENABLED=false
CUTCTX_SENTRY_DSN=""
```

Once running, the proxy will operate indefinitely with full RBAC, memory extraction, and context compression capabilities.
