import json
import os
import re

from cutctx.compress import compress


def test_json_compression():
    print("--- 1. SmartCrusher (JSON Compression) ---")
    bloated_json = {
        "repository": "facebook/react",
        "pull_request": {
            "id": 12345,
            "title": "Fix memory leak in hooks",
            "commits": []
        }
    }
    # Simulate a massive array of commits
    for i in range(500):
        bloated_json["pull_request"]["commits"].append({
            "sha": f"dummy_sha_{i}x"*10,
            "author": {"name": "Test User", "email": "test@example.com", "verified": False},
            "message": "Update something minor",
            "null_field_1": None,
            "null_field_2": None,
            "redundant_tags": ["bug", "fix", "minor", "test", "ci"] * 5
        })

    messages = [{"role": "user", "content": json.dumps(bloated_json)}]
    raw_length = len(messages[0]["content"])

    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)

    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("--------------------------------\\n")

def test_code_compression():
    print("--- 2. CodeCompressor (AST-Aware) ---")
    file_path = os.path.join(os.path.dirname(__file__), "cutctx", "compress.py")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, encoding="utf-8") as f:
        real_code = f.read()

    messages = [{"role": "user", "content": f"```python\\n{real_code}\\n```"}]
    raw_length = len(messages[0]["content"])

    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)

    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("--------------------------------\\n")

def test_log_compression():
    print("--- 3. LogCompressor (Pattern-Detection) ---")
    log_chunk = """
2023-10-27 10:00:01.001 INFO  [main] org.springframework.boot.StartupInfoLogger - Starting Application v1.0.0
2023-10-27 10:00:01.050 DEBUG [main] org.springframework.core.env.StandardEnvironment - Activating profiles []
2023-10-27 10:00:01.100 INFO  [main] org.springframework.context.support.PostProcessorRegistrationDelegate - Bean registration successful
"""
    error_chunk = """
2023-10-27 10:00:02.500 ERROR [main] com.example.service.UserService - FATAL: User lookup failed!
java.lang.NullPointerException: null
    at com.example.service.UserService.getUser(UserService.java:45)
    at com.example.controller.UserController.fetch(UserController.java:22)
    at org.springframework.web.servlet.FrameworkServlet.processRequest(FrameworkServlet.java:1006)
    at org.springframework.web.servlet.FrameworkServlet.doGet(FrameworkServlet.java:898)
    at javax.servlet.http.HttpServlet.service(HttpServlet.java:626)
    at org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:883)
"""
    messy_log = (log_chunk * 100) + error_chunk + (log_chunk * 100)

    messages = [{"role": "user", "content": f"```log\\n{messy_log}\\n```"}]
    raw_length = len(messages[0]["content"])

    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)

    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("--------------------------------\\n")

def test_diff_compression():
    print("--- 4. DiffCompressor (Diff-Aware) ---")
    context_lines = "\\n".join([f" unchanged context line {i}" for i in range(100)])
    diff_payload = f"""
diff --git a/src/main.py b/src/main.py
index 83db48f..9a32c21 100644
--- a/src/main.py
+++ b/src/main.py
@@ -100,50 +100,50 @@
{context_lines}
-    old_function_call()
+    new_function_call(optimized=True)
{context_lines}
"""
    # Repeat the diff structure to make it huge
    massive_diff = diff_payload * 10
    messages = [{"role": "user", "content": f"```diff\\n{massive_diff}\\n```"}]
    raw_length = len(messages[0]["content"])

    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)

    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("--------------------------------\\n")

def test_ccr_and_text():
    print("--- 5. Kompress-Base / CCR Reversibility ---")
    original_text = "The quick brown fox jumps over the lazy dog. " * 500
    messages = [{"role": "user", "content": original_text}]

    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]

    print(f"Original length: {len(original_text)}, Compressed length: {len(compressed_text)}")
    print(f"Transforms applied: {result.transforms_applied}")

    match = re.search(r'hash=([a-zA-Z0-9_-]+)', compressed_text)
    if not match:
        match = re.search(r'ccr_id[=":\\s]+([a-zA-Z0-9_-]+)', compressed_text)
    if not match:
        match = re.search(r'<ccr id="([^"]+)">', compressed_text)

    if match:
        print(f"Found CCR ID marker: {match.group(1)}")
    else:
        print("Could not find CCR marker in output.")
    print("--------------------------------\\n")

def test_semantic_dedup():
    print("--- 6. Semantic Deduplication / Memory ---")
    # We will simulate deduplication by using SharedContext if available,
    # or by pushing the identical payload twice and watching for pointer replacement.
    payload = "Highly specific internal memory deduplication payload block 99283 " * 100

    # Session 1
    messages_1 = [{"role": "user", "content": payload}]
    res1 = compress(messages_1, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    len1 = len(res1.messages[0]["content"])

    # Session 2
    messages_2 = [{"role": "user", "content": payload}]
    res2 = compress(messages_2, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    len2 = len(res2.messages[0]["content"])

    print(f"First pass compressed length: {len1}")
    print(f"Second pass compressed length: {len2}")
    if len2 < len1 and len2 < 200:
        print("Semantic dedup triggered - payload replaced with pointer!")
    else:
        print("Semantic dedup didn't drastically reduce the second pass beyond the first. It might require explicit Session IDs.")
    print("--------------------------------\\n")

def main():
    # Disable telemetry to avoid the SQLite UNIQUE constraint error we found earlier!
    os.environ["CUTCTX_TELEMETRY_DISABLED"] = "1"
    os.environ["CUTCTX_TELEMETRY_DISABLED"] = "1"

    test_json_compression()
    test_code_compression()
    test_log_compression()
    test_diff_compression()
    test_ccr_and_text()
    test_semantic_dedup()

if __name__ == "__main__":
    main()
