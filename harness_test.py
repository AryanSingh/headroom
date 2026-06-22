import os
import requests
import time
import subprocess
import signal
import sys
import json


# We will start the proxy via subprocess so it runs on port 8787
def start_cutctx_proxy():
    print("Starting CutCtx proxy on :8787...")
    # Using python -m headroom.cli.proxy or cutctx proxy
    # For testing, we just run the CLI command
    env = os.environ.copy()
    env["HEADROOM_TELEMETRY_DISABLED"] = "1"
    env["CUTCTX_TELEMETRY_DISABLED"] = "1"
    # Ensure it's not overriding real keys if possible, though for proxy it might need them if forwarding.
    # We will use "mock" upstream if possible. Wait, if it requires valid upstream, we'll get a 401. 
    # But the proxy processes compression *before* sending upstream. 
    # So even if we get 401 from OpenAI, the proxy logs/compression should have triggered!
    proc = subprocess.Popen(
        [".venv/bin/cutctx", "proxy", "--port", "8787"],
        env=env,
        cwd=os.path.abspath(os.path.dirname(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(4) # Wait for startup
    return proc

def test_codex_openai_harness():
    print("--- Testing Codex/OpenAI Harness ---")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer mock-key-for-test"
    }
    # Send a massive code payload to the proxy's OpenAI compatible endpoint
    massive_code = "def foo():\\n    pass\\n" * 500
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": f"Review this code:\\n```python\\n{massive_code}\\n```"}
        ]
    }
    
    try:
        # We send it to localhost:8787 which should be intercepting OpenAI format
        resp = requests.post("http://localhost:8787/v1/chat/completions", headers=headers, json=payload, timeout=10)
        # Even if 401, the proxy intercepted it. We check headers for headroom indicators.
        print(f"Status Code: {resp.status_code}")
        if "x-headroom-saved-tokens" in resp.headers or "x-cutctx-saved-tokens" in resp.headers:
            print("✅ Proxy intercepted and returned CutCtx savings headers!")
        else:
            print("Response Headers:", resp.headers)
            print("Note: Proxy might not inject headers on 401, but the request was routed through.")
    except Exception as e:
        print(f"Error connecting to proxy: {e}")

def test_claude_anthropic_harness():
    print("--- Testing Claude/Anthropic Harness ---")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "mock-key-for-test",
        "anthropic-version": "2023-06-01"
    }
    massive_text = "Here is some large context that should trigger compression. " * 500
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": massive_text}
        ]
    }
    try:
        resp = requests.post("http://localhost:8787/v1/messages", headers=headers, json=payload, timeout=10)
        print(f"Status Code: {resp.status_code}")
        # Again, likely 401, but validates routing
    except Exception as e:
        print(f"Error: {e}")

def main():
    proc = start_cutctx_proxy()
    try:
        test_codex_openai_harness()
        test_claude_anthropic_harness()
    finally:
        print("Shutting down proxy...")
        proc.terminate()
        proc.wait()
        out, err = proc.communicate()
        if "Compressed" in err or "Compressed" in out or "router:" in err or "router:" in out:
            print("✅ Verified compression triggers in proxy stdout/stderr logs!")
            # print snippet of logs
            for line in (out + err).split('\\n'):
                if 'compress' in line.lower() or 'router:' in line.lower():
                    print("  LOG:", line)
        else:
            print("No compression logs found. They might be structured or silent on 401.")

if __name__ == "__main__":
    main()
