import json
import uuid
import re
from headroom.compress import compress

def test_json_compression():
    print("--- 1. JSON Compression Test ---")
    bloated_json = {
        "metadata": {"source": "adversarial_test", "timestamp": "2023-10-27T10:00:00Z", "version": "1.0.0"},
        "data": [
            {"id": i, "name": f"item_{i}", "value": None, "nested": {"redundant": "text"*10}, "tags": ["a", "b", "c"]}
            for i in range(100)
        ]
    }
    messages = [{"role": "user", "content": json.dumps(bloated_json)}]
    raw_length = len(messages[0]["content"])
    
    result = compress(messages, compress_user_messages=True)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)
    
    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    
    # Try parsing the compressed output to see if it's still structured or if it's raw text
    print("Output preview:", compressed_text[:100] + "...")
    print("--------------------------------\\n")


def test_ast_compression():
    print("--- 2. AST Code Compression Test ---")
    messy_code = """
\"\"\"
This is a massive module docstring that explains literally nothing but takes up a ton of tokens.
It goes on and on.
And on.
\"\"\"

import os
import sys
import json
import uuid  # Unused imports

class MassiveClassWithNoPurpose:
    \"\"\"Docstring for MassiveClassWithNoPurpose.\"\"\"
    
    def __init__(self):
        self.x = 1
        self.y = 2
        # A really long useless comment
        # A really long useless comment
        # A really long useless comment
        
    def do_nothing(self):
        \"\"\"This function does nothing.\"\"\"
        pass
        
def core_logic_function(a, b):
    \"\"\"This is the actual important part.\"\"\"
    if a > b:
        return a + b
    else:
        return a - b
        
# Another useless comment block
\"\"\"
More useless strings
\"\"\"
""" * 10 # Multiply to make it huge
    
    messages = [{"role": "user", "content": f"```python\n{messy_code}\n```"}]
    raw_length = len(messages[0]["content"])
    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)
    
    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("Output preview:", compressed_text[:100].replace('\n', ' ') + "...")
    print("--------------------------------\\n")


def test_log_compression():
    print("--- 3. Log Compression Test ---")
    messy_log = """
[2023-10-27T10:00:00.000Z] INFO [main] com.example.MyClass - Starting up...
[2023-10-27T10:00:00.100Z] DEBUG [main] com.example.MyClass - Loading config
[2023-10-27T10:00:00.200Z] DEBUG [main] com.example.MyClass - Config loaded successfully
[2023-10-27T10:00:00.300Z] INFO [main] com.example.MyClass - Connecting to database
[2023-10-27T10:00:00.400Z] DEBUG [main] com.example.MyClass - Connection pool created
[2023-10-27T10:00:00.500Z] WARN [main] com.example.MyClass - Retrying connection (1/3)
[2023-10-27T10:00:00.600Z] WARN [main] com.example.MyClass - Retrying connection (2/3)
[2023-10-27T10:00:00.700Z] WARN [main] com.example.MyClass - Retrying connection (3/3)
[2023-10-27T10:00:00.800Z] ERROR [main] com.example.MyClass - FATAL: Database connection failed!
java.sql.SQLException: Connection refused
    at com.example.db.ConnectionFactory.create(ConnectionFactory.java:45)
    at com.example.db.ConnectionPool.init(ConnectionPool.java:120)
    at com.example.MyClass.start(MyClass.java:88)
    at com.example.Main.main(Main.java:15)
[2023-10-27T10:00:00.900Z] INFO [main] com.example.MyClass - Shutting down...
""" * 50
    
    messages = [{"role": "user", "content": f"```log\n{messy_log}\n```"}]
    raw_length = len(messages[0]["content"])
    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    comp_length = len(compressed_text)
    
    print(f"Raw length: {raw_length}, Compressed length: {comp_length}")
    print(f"Savings: {100 - (comp_length/raw_length)*100:.2f}%")
    print(f"Transforms applied: {result.transforms_applied}")
    print("Output preview (check if FATAL is kept):")
    print(compressed_text[:300])
    print("--------------------------------\\n")


def test_ccr_reversibility():
    print("--- 4. CCR Reversibility Test ---")
    original_text = "This is a very specific sentence that must be exactly recovered. " * 50
    messages = [{"role": "user", "content": original_text}]
    result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
    compressed_text = result.messages[0]["content"]
    
    print(f"Original length: {len(original_text)}, Compressed length: {len(compressed_text)}")
    print(f"Compressed text output: {compressed_text}")
    
    # Extract CCR ID (it usually looks like <ccr id="xyz">...</ccr> or similar)
    match = re.search(r'hash=([a-zA-Z0-9_-]+)', compressed_text)
    if not match:
        match = re.search(r'ccr_id[=":\s]+([a-zA-Z0-9_-]+)', compressed_text)
    if not match:
        match = re.search(r'<ccr id="([^"]+)">', compressed_text)
        
    if match:
        ccr_id = match.group(1)
        print(f"Found CCR ID: {ccr_id}")
        print("Reversibility marker successfully injected by compressor.")
    else:
        print("Could not find CCR ID in compressed text. Might be using a different output format or it wasn't triggered.")
    print("--------------------------------\\n")


def main():
    test_json_compression()
    test_ast_compression()
    test_log_compression()
    test_ccr_reversibility()

if __name__ == "__main__":
    main()
