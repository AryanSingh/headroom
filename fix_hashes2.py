import re
with open("tests/test_ccr_tool_injection.py", "r") as f:
    content = f.read()

def replacer(match):
    full_hash = match.group(1)
    # keep first 16 chars
    return full_hash[:16]

content = re.sub(r'([a-fA-F0-9]{24})', replacer, content)
content = content.replace("test_accepts_valid_24_char_hash", "test_accepts_valid_16_char_hash")
content = content.replace("24 chars", "16 chars")
content = content.replace("exactly 24 hex", "exactly 16 hex")

with open("tests/test_ccr_tool_injection.py", "w") as f:
    f.write(content)
