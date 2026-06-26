import json

from cutctx.compress import compress

large_json = json.dumps([{"id": i, "val": "hello world"} for i in range(1000)])

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": large_json},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
                }
            }
        ]
    }
]

print("Running compress...")
try:
    res = compress(messages, optimize=True, model="gpt-4o", compress_user_messages=True, target_ratio=0.5)
    print("Success! Output texts:")
    for block in res.messages[-1]["content"]:
        if block["type"] == "text":
            print("Text length:", len(block["text"]))
        else:
            print("Block type:", block["type"])
    print(f"Tokens before: {res.tokens_before}, after: {res.tokens_after}")
except Exception:
    import traceback
    traceback.print_exc()
