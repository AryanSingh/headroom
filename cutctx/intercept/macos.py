"""macOS transparent HTTPS interception for cutctx proxy.

How it works:
1. mkcert generates a locally-trusted CA + TLS cert for AI API domains.
2. /etc/hosts redirects those domains to 127.0.0.1.
3. pfctl forwards port 443 → cutctx proxy port (default 8787).
4. The proxy starts with the mkcert TLS cert so it terminates HTTPS correctly.

Result: every app on the machine — Claude Desktop, Cursor, VS Code, browsers —
routes AI API calls through cutctx regardless of hardcoded base URLs.
"""

from __future__ import annotations

import json
import plistlib
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

INTERCEPT_DOMAINS: list[str] = [
    "api.anthropic.com",
    "api.openai.com",
]

_HOSTS_START = "# cutctx-intercept-start"
_HOSTS_END = "# cutctx-intercept-end"

_PROXY_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.cutctx.proxy.plist"
_PF_DAEMON_LABEL = "com.cutctx.pf"
_PF_DAEMON_PLIST = Path(f"/Library/LaunchDaemons/{_PF_DAEMON_LABEL}.plist")

CERTS_DIR = Path.home() / ".cutctx" / "certs"
_BYPASS_IPS_FILE = Path.home() / ".cutctx" / "intercept_bypass_ips.json"


def _run(
    cmd: Sequence[str | Path],
    *,
    sudo: bool = False,
    input: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    full_cmd = (["sudo"] + [str(c) for c in cmd]) if sudo else [str(c) for c in cmd]
    return subprocess.run(full_cmd, input=input, capture_output=True, text=True, check=check)


def _osascript_sudo(shell_cmd: str, description: str = "cutctx requires administrator access") -> None:
    """Run a shell command with GUI admin privileges via macOS osascript dialog."""
    escaped = shell_cmd.replace('"', '\\"').replace("'", "'\\''")
    script = f'do shell script "{escaped}" with administrator privileges with prompt "{description}"'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Admin command failed (user may have cancelled).\n"
            f"stderr: {result.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# mkcert
# ---------------------------------------------------------------------------

def ensure_mkcert() -> Path:
    path = shutil.which("mkcert")
    if path:
        return Path(path)
    if not shutil.which("brew"):
        raise RuntimeError(
            "Homebrew is required to install mkcert. "
            "Install from https://brew.sh, then run `cutctx intercept install` again."
        )
    print("Installing mkcert via Homebrew…")
    subprocess.run(["brew", "install", "mkcert"], check=True)
    path = shutil.which("mkcert")
    if not path:
        raise RuntimeError("mkcert not found after `brew install mkcert`.")
    return Path(path)


def install_local_ca(mkcert: Path) -> None:
    """Install the mkcert CA into the macOS system keychain.

    mkcert -install calls `security add-trusted-cert` which requires a real
    interactive terminal session. Opens Terminal.app to run it, then polls
    until the CA becomes trusted (up to 120 seconds).
    """
    import time

    print("Installing local CA in macOS Keychain…")
    print("  → A Terminal window will open. Enter your password there.")
    applescript = (
        f'tell application "Terminal"\n'
        f'  activate\n'
        f'  do script "{mkcert} -install && echo MKCERT_DONE"\n'
        f'end tell'
    )
    subprocess.run(["osascript", "-e", applescript], check=False)
    print("  Waiting for mkcert -install to complete", end="", flush=True)
    for _ in range(60):  # poll up to 120 s
        time.sleep(2)
        if is_ca_installed(mkcert):
            print(" ✓")
            return
        print(".", end="", flush=True)
    print()
    raise RuntimeError(
        "Timed out waiting for mkcert -install.\n"
        "Please run `mkcert -install` in a Terminal window and then re-run "
        "`cutctx intercept install`."
    )


def is_ca_installed(mkcert: Path) -> bool:
    """Return True if the mkcert local CA cert exists AND is trusted by the OS."""
    caroot_result = subprocess.run(
        [str(mkcert), "-CAROOT"], capture_output=True, text=True, check=False
    )
    if caroot_result.returncode != 0:
        return False
    caroot = caroot_result.stdout.strip()
    ca_cert = Path(caroot) / "rootCA.pem"
    if not ca_cert.exists():
        return False
    # security verify-cert returns 0 only if the cert is trusted
    result = subprocess.run(
        ["security", "verify-cert", "-c", str(ca_cert)],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def generate_certs(mkcert: Path, domains: list[str]) -> tuple[Path, Path]:
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    cert_file = CERTS_DIR / "intercept.pem"
    key_file = CERTS_DIR / "intercept-key.pem"
    print(f"Generating TLS certificate for: {', '.join(domains)}")
    subprocess.run(
        [str(mkcert), "-cert-file", str(cert_file), "-key-file", str(key_file)] + domains,
        check=True,
    )
    return cert_file, key_file


def pre_resolve_ips(domains: list[str]) -> dict[str, str]:
    """Resolve real IPs for domains *before* /etc/hosts is modified.

    Saves the result to ~/.cutctx/intercept_bypass_ips.json so the proxy
    can bypass /etc/hosts when making its own outbound connections to these
    domains (preventing the redirect loop).
    """
    ips: dict[str, str] = {}
    for domain in domains:
        try:
            results = socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM)
            if results:
                ips[domain] = results[0][4][0]
        except OSError:
            pass
    _BYPASS_IPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BYPASS_IPS_FILE.write_text(json.dumps(ips, indent=2))
    return ips


def remove_bypass_ips() -> None:
    _BYPASS_IPS_FILE.unlink(missing_ok=True)


def mkcert_ca_path(mkcert: Path) -> Path | None:
    """Return the path to the mkcert root CA certificate, if it exists."""
    result = subprocess.run(
        [str(mkcert), "-CAROOT"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    caroot = result.stdout.strip()
    ca_cert = Path(caroot) / "rootCA.pem"
    return ca_cert if ca_cert.exists() else None


def setup_node_tls_trust(mkcert: Path) -> Path | None:
    """Set NODE_EXTRA_CA_CERTS in launchctl so Node.js trusts the mkcert CA.

    This makes Claude Code (Node.js) accept the mkcert TLS certificate
    presented by the proxy during transparent interception — without needing
    `mkcert -install` or any keychain interaction.
    """
    ca_path = mkcert_ca_path(mkcert)
    if ca_path is None:
        return None
    subprocess.run(
        ["launchctl", "setenv", "NODE_EXTRA_CA_CERTS", str(ca_path)],
        check=False,
    )
    return ca_path


def remove_node_tls_trust() -> None:
    subprocess.run(
        ["launchctl", "unsetenv", "NODE_EXTRA_CA_CERTS"],
        check=False,
    )


# ---------------------------------------------------------------------------
# /etc/hosts
# ---------------------------------------------------------------------------

def _hosts_block(domains: list[str]) -> str:
    lines = [_HOSTS_START]
    for d in domains:
        lines.append(f"127.0.0.1 {d}")
    lines.append(_HOSTS_END)
    return "\n".join(lines) + "\n"


def _strip_hosts_block(content: str) -> str:
    return re.sub(
        rf"{re.escape(_HOSTS_START)}.*?{re.escape(_HOSTS_END)}\n?",
        "",
        content,
        flags=re.DOTALL,
    )


def install_hosts_entries(domains: list[str]) -> None:
    print("Adding /etc/hosts entries (will prompt for password)…")
    hosts = Path("/etc/hosts")
    content = _strip_hosts_block(hosts.read_text()).rstrip("\n") + "\n"
    content += _hosts_block(domains)
    # Write to a temp file the current user owns, then copy with admin privs
    tmp = Path("/tmp/cutctx_hosts_tmp")
    tmp.write_text(content)
    _osascript_sudo(
        f"cp {tmp} /etc/hosts && dscacheutil -flushcache && killall -HUP mDNSResponder",
        description="cutctx needs to update /etc/hosts to redirect AI API domains to the local proxy",
    )
    tmp.unlink(missing_ok=True)


def remove_hosts_entries() -> None:
    print("Removing /etc/hosts entries (will prompt for password)…")
    hosts = Path("/etc/hosts")
    content = _strip_hosts_block(hosts.read_text())
    tmp = Path("/tmp/cutctx_hosts_tmp")
    tmp.write_text(content)
    _osascript_sudo(
        f"cp {tmp} /etc/hosts && dscacheutil -flushcache && killall -HUP mDNSResponder",
        description="cutctx needs to update /etc/hosts to remove proxy redirect entries",
    )
    tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# pfctl port forwarding  443 → proxy_port
# ---------------------------------------------------------------------------

def _pf_rule(proxy_port: int) -> str:
    return f"rdr pass on lo0 proto tcp from any to 127.0.0.1 port 443 -> 127.0.0.1 port {proxy_port}"


def _pf_daemon_plist(proxy_port: int) -> str:
    rule = _pf_rule(proxy_port)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_PF_DAEMON_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>echo "{rule}" | /sbin/pfctl -ef -</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""


def install_pfctl_forwarding(proxy_port: int) -> None:
    print(f"Setting up port forwarding 443 → {proxy_port} (will prompt for password)…")

    # Write the pf rule and LaunchDaemon plist to temp files
    rule = _pf_rule(proxy_port)
    plist_content = _pf_daemon_plist(proxy_port)

    tmp_rule = Path("/tmp/cutctx_pf_rule.conf")
    tmp_plist = Path("/tmp/com.cutctx.pf.plist")
    tmp_rule.write_text(rule + "\n")
    tmp_plist.write_text(plist_content)

    daemon_plist = str(_PF_DAEMON_PLIST)
    _osascript_sudo(
        f"pfctl -ef {tmp_rule} ; "
        f"cp {tmp_plist} {daemon_plist} && "
        f"chown root:wheel {daemon_plist} && "
        f"chmod 644 {daemon_plist} && "
        f"launchctl unload {daemon_plist} 2>/dev/null ; "
        f"launchctl load {daemon_plist}",
        description=f"cutctx needs to forward port 443 → {proxy_port} to intercept HTTPS API traffic",
    )
    tmp_rule.unlink(missing_ok=True)
    tmp_plist.unlink(missing_ok=True)


def remove_pfctl_forwarding() -> None:
    print("Removing port forwarding (will prompt for password)…")
    daemon_plist = str(_PF_DAEMON_PLIST)
    _osascript_sudo(
        f"launchctl unload {daemon_plist} 2>/dev/null ; "
        f"rm -f {daemon_plist} ; "
        f"pfctl -F nat 2>/dev/null ; true",
        description="cutctx needs to remove the port 443 forwarding rule",
    )


# ---------------------------------------------------------------------------
# LaunchAgent (com.cutctx.proxy.plist) TLS update
# ---------------------------------------------------------------------------

def update_launchagent_tls(cert_file: Path, key_file: Path, ca_path: Path | None = None) -> bool:
    if not _PROXY_PLIST.exists():
        return False
    with open(_PROXY_PLIST, "rb") as f:
        plist = plistlib.load(f)
    args: list[str] = plist.get("ProgramArguments", [])
    # Fix stale binary path if it no longer exists
    if args and not Path(args[0]).exists():
        resolved = shutil.which("cutctx")
        if resolved:
            args[0] = resolved
    # Strip any existing --tls-cert / --tls-key pairs
    clean: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--tls-cert", "--tls-key"):
            i += 2
        else:
            clean.append(args[i])
            i += 1
    clean += ["--tls-cert", str(cert_file), "--tls-key", str(key_file)]
    plist["ProgramArguments"] = clean
    # Persist NODE_EXTRA_CA_CERTS so the proxy trusts mkcert CA on restart
    if ca_path is not None:
        env: dict = plist.setdefault("EnvironmentVariables", {})
        env["NODE_EXTRA_CA_CERTS"] = str(ca_path)
    with open(_PROXY_PLIST, "wb") as f:
        plistlib.dump(plist, f)
    _reload_launchagent()
    return True


def remove_launchagent_tls() -> bool:
    if not _PROXY_PLIST.exists():
        return False
    with open(_PROXY_PLIST, "rb") as f:
        plist = plistlib.load(f)
    args: list[str] = plist.get("ProgramArguments", [])
    clean: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--tls-cert", "--tls-key"):
            i += 2
        else:
            clean.append(args[i])
            i += 1
    plist["ProgramArguments"] = clean
    env: dict = plist.get("EnvironmentVariables", {})
    env.pop("NODE_EXTRA_CA_CERTS", None)
    with open(_PROXY_PLIST, "wb") as f:
        plistlib.dump(plist, f)
    _reload_launchagent()
    return True


def _reload_launchagent() -> None:
    subprocess.run(
        ["launchctl", "unload", str(_PROXY_PLIST)], capture_output=True, check=False
    )
    subprocess.run(
        ["launchctl", "load", str(_PROXY_PLIST)], capture_output=True, check=False
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def status() -> dict:
    hosts_content = Path("/etc/hosts").read_text() if Path("/etc/hosts").exists() else ""
    cert_file = CERTS_DIR / "intercept.pem"
    node_ca = subprocess.run(
        ["launchctl", "getenv", "NODE_EXTRA_CA_CERTS"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    return {
        "hosts_entries": _HOSTS_START in hosts_content,
        "pf_daemon": _PF_DAEMON_PLIST.exists(),
        "tls_cert": cert_file.exists(),
        "launchagent_tls": _launchagent_has_tls(),
        "bypass_ips": _BYPASS_IPS_FILE.exists(),
        "node_tls_trust": bool(node_ca and Path(node_ca).exists()),
    }


def _launchagent_has_tls() -> bool:
    if not _PROXY_PLIST.exists():
        return False
    with open(_PROXY_PLIST, "rb") as f:
        plist = plistlib.load(f)
    return "--tls-cert" in plist.get("ProgramArguments", [])


def assert_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("cutctx intercept is only supported on macOS.")
