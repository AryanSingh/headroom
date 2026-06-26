import asyncio
import time

from cutctx.ccr.batch_store import BatchContext, BatchContextStore, BatchRequestContext


async def main():
    now = 200.0

    # Store old time.time
    old_time = time.time
    import cutctx.ccr.batch_store
    cutctx.ccr.batch_store.time.time = lambda: now

    store = BatchContextStore(ttl=5, max_contexts=10)
    first = BatchContext(batch_id="b1", provider="anthropic")
    first.add_request(
        BatchRequestContext(custom_id="r1", messages=[{"content": "alpha"}], tools=[])
    )
    await store.store(first)
    print("first expires_at:", first.expires_at)

    now = 200.0 + 86400.0 + 10.0
    expired = await store.cleanup_expired()
    print("expired:", expired)

    cutctx.ccr.batch_store.time.time = old_time

asyncio.run(main())
