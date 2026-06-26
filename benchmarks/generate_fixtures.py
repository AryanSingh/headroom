"""Generate benchmark fixture texts from synthetic data.

Creates representative .txt files in benchmarks/fixtures/ that simulate
real-world agent workloads (code, logs, documentation, JSON payloads).
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path("benchmarks/fixtures")


def generate_code_fixture() -> str:
    """Simulate a Python codebase with imports, classes, and functions."""
    lines = [
        '"""Module for handling user authentication and authorization."""',
        "import hashlib",
        "import os",
        "import time",
        "from typing import Optional, Dict, Any",
        "",
        "from cutctx.security import validate_token",
        "from cutctx.models import User, Session",
        "",
        "",
        "class AuthManager:",
        '    """Manages user authentication, token validation, and session lifecycle."""',
        "",
        "    def __init__(self, secret_key: str, token_ttl: int = 3600):",
        "        self.secret_key = secret_key",
        "        self.token_ttl = token_ttl",
        "        self._sessions: Dict[str, Session] = {}",
        "",
        "    def authenticate(self, username: str, password: str) -> Optional[str]:",
        '        """Authenticate user and return a JWT token."""',
        "        user = self._lookup_user(username)",
        "        if user is None:",
        "            return None",
        "        if not self._verify_password(password, user.password_hash):",
        "            return None",
        "        token = self._generate_token(user)",
        "        self._sessions[token] = Session(user_id=user.id, created_at=time.time())",
        "        return token",
        "",
        "    def validate(self, token: str) -> Optional[User]:",
        '        """Validate a token and return the associated user."""',
        "        if token not in self._sessions:",
        "            return None",
        "        session = self._sessions[token]",
        "        if time.time() - session.created_at > self.token_ttl:",
        "            del self._sessions[token]",
        "            return None",
        "        return self._lookup_user_by_id(session.user_id)",
        "",
        "    def revoke(self, token: str) -> bool:",
        '        """Revoke an active session."""',
        "        if token in self._sessions:",
        "            del self._sessions[token]",
        "            return True",
        "        return False",
        "",
        "    def _generate_token(self, user: User) -> str:",
        "        payload = f'{user.id}:{time.time()}'",
        "        return hashlib.sha256(payload.encode()).hexdigest()",
        "",
        "    def _verify_password(self, password: str, password_hash: str) -> bool:",
        "        return hashlib.sha256(password.encode()).hexdigest() == password_hash",
        "",
        "    def _lookup_user(self, username: str) -> Optional[User]:",
        "        # In production, this queries the database",
        "        return None",
        "",
        "    def _lookup_user_by_id(self, user_id: str) -> Optional[User]:",
        "        return None",
        "",
        "",
        "def create_auth_manager() -> AuthManager:",
        '    """Factory function using environment variables."""',
        "    secret = os.environ.get('AUTH_SECRET_KEY', 'dev-secret')",
        "    ttl = int(os.environ.get('AUTH_TOKEN_TTL', '3600'))",
        "    return AuthManager(secret_key=secret, token_ttl=ttl)",
    ]
    return "\n".join(lines)


def generate_log_fixture() -> str:
    """Simulate application logs with errors and warnings."""
    lines = [
        "2025-01-15T10:30:01Z INFO  [main] Application starting on port 8080",
        "2025-01-15T10:30:01Z INFO  [db] Connecting to PostgreSQL at db.internal:5432",
        "2025-01-15T10:30:02Z INFO  [db] Connected successfully (pool_size=10)",
        "2025-01-15T10:30:02Z INFO  [cache] Redis connected at cache.internal:6379",
        "2025-01-15T10:30:05Z INFO  [http] Server listening on 0.0.0.0:8080",
        "2025-01-15T10:30:15Z WARN  [auth] Failed login attempt from 192.168.1.100 (user=admin)",
        "2025-01-15T10:30:16Z WARN  [auth] Failed login attempt from 192.168.1.100 (user=admin)",
        "2025-01-15T10:30:17Z ERROR [auth] IP 192.168.1.100 blocked after 3 failed attempts",
        "2025-01-15T10:31:00Z INFO  [api] POST /v1/users 201 12ms",
        "2025-01-15T10:31:01Z INFO  [api] GET /v1/users/123 200 8ms",
        "2025-01-15T10:31:05Z WARN  [db] Slow query detected (2341ms): SELECT * FROM orders WHERE status = 'pending'",
        "2025-01-15T10:31:10Z INFO  [api] POST /v1/orders 201 45ms",
        "2025-01-15T10:32:00Z ERROR [worker] Task queue depth exceeded threshold: 1500/1000",
        "2025-01-15T10:32:01Z INFO  [worker] Scaling up workers from 4 to 8",
        "2025-01-15T10:32:30Z INFO  [worker] Queue depth normalized: 450/1000",
        "2025-01-15T10:33:00Z INFO  [api] GET /v1/dashboard 200 156ms",
        "2025-01-15T10:33:05Z WARN  [cache] Cache miss rate high: 45% (threshold: 30%)",
        "2025-01-15T10:34:00Z INFO  [metrics] Requests/min: 1234, Avg latency: 23ms, P99: 89ms",
        "2025-01-15T10:35:00Z INFO  [db] Connection pool stats: active=7, idle=3, waiting=0",
        "2025-01-15T10:35:00Z INFO  [main] Health check: OK (uptime: 5m, memory: 256MB)",
    ]
    return "\n".join(lines)


def generate_json_fixture() -> str:
    """Simulate large JSON API payloads."""
    import json

    data = {
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "role": ["admin", "editor", "viewer"][i % 3],
                "settings": {
                    "theme": "dark",
                    "notifications": True,
                    "language": "en",
                    "timezone": "UTC",
                },
                "metadata": {
                    "last_login": "2025-01-15T10:00:00Z",
                    "login_count": i * 10,
                    "preferences": {"compact_view": True, "auto_save": True},
                },
            }
            for i in range(100)
        ],
        "pagination": {"page": 1, "per_page": 100, "total": 1000, "total_pages": 10},
    }
    return json.dumps(data, indent=2)


def generate_markdown_fixture() -> str:
    """Simulate a large documentation file."""
    sections = []
    sections.append("# Cutctx Documentation\n")
    sections.append("## Overview\n")
    sections.append(
        "Cutctx is an open-source context compression layer for AI agents. "
        "It reduces token usage by 60-95% while maintaining data integrity "
        "through reversible compression.\n"
    )

    for i in range(20):
        sections.append(f"## Section {i + 1}: Feature Description\n")
        sections.append(
            f"This section describes feature {i + 1} of Cutctx. "
            f"The feature provides compression capabilities that reduce "
            f"token consumption for AI agent interactions. Key benefits include "
            f"cost reduction, latency improvement, and context window optimization. "
            f"The implementation uses advanced algorithms including SmartCrusher for "
            f"JSON compression, CodeCompressor for source code, and DiffCompressor "
            f"for diff/patch content.\n"
        )
        sections.append("### Usage\n")
        sections.append(
            "```bash\ncutctx proxy --port 8787 --compression-mode live-zone\n```\n"
        )
        sections.append("### Configuration\n")
        sections.append(
            "| Setting | Default | Description |\n"
            "|---------|---------|-------------|\n"
            "| `max_body_mb` | 50 | Maximum request body size |\n"
            "| `compression_mode` | live-zone | Compression strategy |\n"
        )

    return "\n".join(sections)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    fixtures = {
        "code_authentication.py": generate_code_fixture,
        "application_logs.txt": generate_log_fixture,
        "api_users_payload.json": generate_json_fixture,
        "documentation.md": generate_markdown_fixture,
    }

    for filename, generator in fixtures.items():
        path = FIXTURES_DIR / filename
        path.write_text(generator(), encoding="utf-8")
        print(f"  Created {path} ({path.stat().st_size:,} bytes)")

    print(f"\nGenerated {len(fixtures)} fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
