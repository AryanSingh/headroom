from cutctx.tokenizers.tiktoken_counter import TiktokenCounter

tokenizer = TiktokenCounter("gpt-4o")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "What is in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
                }
            }
        ]
    }
]

print("Tokens:", tokenizer.count_messages(messages))
