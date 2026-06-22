from headroom.compress import compress
import adversarial_test

print("Log test:")
messages = [{"role": "user", "content": f"```log\n{adversarial_test.test_log_compression.__code__.co_consts[1]}\n```"}]
result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0)
print(result.transforms_applied)
print("Tokens before:", result.tokens_before, "Tokens after:", result.tokens_after)
print(len(result.messages[0]["content"]))
