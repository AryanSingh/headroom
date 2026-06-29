filepath = "/Users/aryansingh/.gemini/antigravity/brain/58dcb762-c4bf-4a0a-afa4-5ff35dcd368d/scratch/verify_features.py"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace("last.get('ghost_tokens', 0)", "last[0] if isinstance(last, list) else last.get('ghost_tokens', 0) if isinstance(last, dict) else last")
content = content.replace("last.get('scaffolding_tokens', 0)", "last[1] if isinstance(last, list) else last.get('scaffolding_tokens', 0) if isinstance(last, dict) else last")
content = content.replace("last.get('api_surface_slimming', 0)", "last")
content = content.replace("last.get('tool_schema_compaction_savings_usd', 0)", "last")

with open(filepath, "w") as f:
    f.write(content)
