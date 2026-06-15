#!/usr/bin/env python3
"""CutCtx stats helper — show compression statistics.

Usage:
    python3 stats.py
    python3 stats.py --json
"""
import argparse
import json
import os


def get_stats(proxy_url: str = None) -> dict:
    """Get compression stats from the proxy."""
    url = proxy_url or os.environ.get("HEADROOM_PROXY_URL", "http://127.0.0.1:8787")
    try:
        import httpx
        response = httpx.get(f"{url}/stats", timeout=5.0)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Proxy returned status {response.status_code}"}
    except ImportError:
        return {"error": "httpx not installed", "install": "pip install httpx"}
    except Exception as e:
        return {"error": str(e), "hint": "Is the proxy running? Start with: headroom proxy"}


def main():
    parser = argparse.ArgumentParser(description="CutCtx compression stats")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--proxy-url", "-p", help="Proxy URL")
    args = parser.parse_args()

    stats = get_stats(args.proxy_url)

    if args.json:
        print(json.dumps(stats, indent=2))
    elif "error" in stats:
        print(f"Error: {stats['error']}")
        if "hint" in stats:
            print(f"Hint: {stats['hint']}")
        if "install" in stats:
            print(f"Install: {stats['install']}")
    else:
        print("CutCtx Session Stats")
        print("=" * 40)
        print(f"Requests:    {stats.get('requests_total', 0)}")
        print(f"Tokens In:   {stats.get('tokens_input_total', 0):,}")
        print(f"Tokens Saved:{stats.get('tokens_saved_total', 0):,}")
        saved = stats.get('tokens_saved_total', 0)
        total = stats.get('tokens_input_total', 0) + saved
        if total > 0:
            pct = (saved / total) * 100
            print(f"Savings:     {pct:.1f}%")


if __name__ == "__main__":
    main()
