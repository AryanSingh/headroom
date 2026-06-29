filepath = "/Users/aryansingh/.gemini/antigravity/brain/58dcb762-c4bf-4a0a-afa4-5ff35dcd368d/scratch/verify_features.py"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace("urllib.request.Request(STATS_URL)", "urllib.request.Request(STATS_URL, headers={'Authorization': 'Bearer 9TrHXJx8qGf5GvVg5fJjUvcCcb2NBZAYR5JKybvew5I'})")

with open(filepath, "w") as f:
    f.write(content)
