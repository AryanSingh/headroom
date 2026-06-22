from headroom.transforms.content_router import ContentRouter
from headroom.compress import compress

messy_log = """
[2023-10-27T10:00:00.000Z] INFO [main] com.example.MyClass - Starting up...
""" * 50

messages = [{"role": "user", "content": f"```log\n{messy_log}\n```"}]
result = compress(messages, compress_user_messages=True, target_ratio=0.1)
print(result.transforms_applied)
print(result.compression_ratio)
