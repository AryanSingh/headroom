import sys

file_path = "/Users/aryansingh/.gemini/antigravity/brain/58dcb762-c4bf-4a0a-afa4-5ff35dcd368d/scratch/verify_features.py"
with open(file_path, "r") as f:
    content = f.read()

content = content.replace('"Authorization": "Bearer fake-test-key"', '"Authorization": "Bearer testkey"')

with open(file_path, "w") as f:
    f.write(content)
