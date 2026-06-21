# 011. Deployment

**Status:** done

## Deployment Profiles

### Docker Profile

**Image:** `cutctx-ai/cutctx:latest`

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

RUN pip install cutctx-ai

EXPOSE 8787

ENTRYPOINT ["cutctx", "proxy"]
CMD ["--host", "0.0.0.0", "--port", "8787"]
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  cutctx:
    image: cutctx-ai/cutctx:latest
    ports:
      - "8787:8787"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CUTCTX_MODE=token
    volumes:
      - cutctx-data:/root/.cutctx

volumes:
  cutctx-data:
```

**Run:**
```bash
docker-compose up -d
```

---

### Native Profile

**Installation:**
```bash
pip install cutctx-ai
```

**Run:**
```bash
cutctx proxy --host 0.0.0.0 --port 8787
```

---

### Embedded Profile

**Usage:**
```python
from cutctx import CutctxClient

client = CutctxClient(
    api_key="your-api-key",
    base_url="http://localhost:8787"
)

result = await client.compress(messages)
```

---

## Cloud Presets

### AWS (EC2/ECS)

```yaml
# ~/.cutctx/config.yaml
deployment:
  profile: aws
  instance_type: t3.medium

compression:
  enabled: true
  max_tokens: 8192

cache:
  backend: redis
  redis_url: redis://localhost:6379
```

### Google Cloud (Cloud Run)

```yaml
deployment:
  profile: gcp
  region: us-central1
  memory: 512Mi
  cpu: 1
```

### Azure (Container Apps)

```yaml
deployment:
  profile: azure
  resource_group: cutctx-rg
```

---

## Runtime Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_MODE` | `token` | Proxy mode (`token` or `cache`) |
| `CUTCTX_PORT` | `8787` | Proxy port |
| `CUTCTX_HOST` | `127.0.0.1` | Proxy host |
| `ANTHROPIC_API_KEY` | - | Anthropic API key |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `CUTCTX_TELEMETRY` | enabled | Set to `off` to disable telemetry |

### Config File

```yaml
# ~/.cutctx/config.yaml
proxy:
  host: 0.0.0.0
  port: 8787

compression:
  enabled: true
  max_tokens: 4096
  overlap_tokens: 512
  content_sensitivity: 0.5
  preserve_system_messages: true
  priority_tokens: 1024

cache:
  enabled: true
  ttl: 3600
  max_size: 10000

telemetry:
  metrics:
    enabled: true
  tracing:
    enabled: false

learn:
  enabled: false
```

---

## Resource Requirements

| Deployment | CPU | Memory | Storage |
|------------|-----|--------|---------|
| Minimal | 0.5 core | 512MB | 1GB |
| Default | 1 core | 1GB | 5GB |
| Enterprise | 2 cores | 2GB | 20GB |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0-draft | 2026-04-16 | Initial deployment document |
