"""Transparent HTTPS interception for cutctx proxy.

Enables cutctx to capture API traffic from apps that hardcode API URLs
(e.g. Claude Desktop overriding ANTHROPIC_BASE_URL when launching Claude Code).

macOS setup:
    cutctx intercept install    # mkcert CA + /etc/hosts + pfctl + LaunchAgent TLS
    cutctx intercept status
    cutctx intercept uninstall
"""
