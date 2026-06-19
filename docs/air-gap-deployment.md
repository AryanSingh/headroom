# CutCtx Air-Gap Deployment Guide

For defense, healthcare, and highly-regulated environments, CutCtx supports a full offline deployment mode with zero outbound internet connectivity requirements.

## 1. Pre-fetching Machine Learning Weights

CutCtx relies on ONNX weights for the AST/semantic compression engine. To run offline, these must be bundled inside the container or mounted to a persistent volume.

1. On an internet-connected machine, download the `kompress-v2-base` model from HuggingFace:
```bash
git lfs install
git clone https://huggingface.co/headroom/kompress-v2-base /opt/headroom/models
```

2. Package the `/opt/headroom/models` directory into a tarball and securely transfer it across the air-gap to the target environment.

3. Set the following environment variable to enforce offline-only model loading:
```env
HF_HUB_OFFLINE=1
HEADROOM_MODEL_CACHE_DIR=/opt/headroom/models
```

## 2. Offline License Validation

Because CutCtx cannot reach the PitchToShip servers for periodic license validation in an air-gapped environment, you must use an offline HMAC-signed license key.

1. Generate your offline key in the PitchToShip vendor portal (Enterprise Tier only).
2. Pass the key to the CutCtx proxy via the environment:
```env
HEADROOM_EE_LICENSE_KEY="ptsk_off_..."
```
*CutCtx uses Ed25519 signature verification (`headroom_ee/billing/license_token.py`) to cryptographically guarantee the validity of the key and its embedded seat constraints without phoning home.*

## 3. Container Images

Use the official `headroom-proxy:latest-distroless` image. Transfer the image to your private, air-gapped container registry:

```bash
# On internet-connected machine
docker pull headroom/proxy:latest-distroless
docker save headroom/proxy:latest-distroless -o headroom.tar

# Transfer headroom.tar across the air-gap

# On air-gapped machine
docker load -i headroom.tar
docker tag headroom/proxy:latest-distroless private-registry.internal.corp/headroom/proxy:latest-distroless
docker push private-registry.internal.corp/headroom/proxy:latest-distroless
```

## 4. Telemetry Disable

OpenTelemetry and external metrics collection should be disabled or routed to an internal sink:
```env
HEADROOM_OTEL_EXPORT_ENABLED=false
HEADROOM_SENTRY_DSN=""
```

Once running, the proxy will operate indefinitely with full RBAC, memory extraction, and context compression capabilities.
