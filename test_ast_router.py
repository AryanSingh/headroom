from cutctx.compress import compress

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
""" * 10

messages = [{"role": "user", "content": f"```python\n{messy_code}\n```"}]
result = compress(messages, compress_user_messages=True, target_ratio=0.1)
print(result.transforms_applied)
