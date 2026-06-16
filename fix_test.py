
with open('tests/test_adapter_hooks.py') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "def test_memory_env_returns_none(self):" in line:
        lines[i] = "    def test_memory_env_returns_none(self, monkeypatch):\n"
    if "with patch.dict" in line:
        pass # We'll replace it entirely

# We can just write a quick script to find the definitions and rewrite them.
