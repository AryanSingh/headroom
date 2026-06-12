import re
with open("tests/test_ccr_tool_injection.py", "r") as f:
    content = f.read()

# Replace 24-char test hashes with 16-char hashes
# b10cf0a2b3c4b10cf0a2b3c4 -> b10cf0a2b3c4b10c
content = content.replace("b10cf0a2b3c4b10cf0a2b3c4", "b10cf0a2b3c4b10c")
content = content.replace("a1b2c3d4e5f6a1b2c3d4e5f6", "a1b2c3d4e5f6a1b2")
content = content.replace("c7d8e9f0a1b2c7d8e9f0a1b2", "c7d8e9f0a1b2c7d8")
content = content.replace("abc123def456abc123def456", "abc123def456abc1")
content = content.replace("abc123def456abc1", "abc123def4567890") # making it a valid hex
content = content.replace("f" * 24, "f" * 16)
content = content.replace("test_accepts_valid_24_char_hash", "test_accepts_valid_16_char_hash")

with open("tests/test_ccr_tool_injection.py", "w") as f:
    f.write(content)
