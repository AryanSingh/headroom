import json

from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig

rows = [
    {
        "id": i,
        "status": "ok",
        "message": "normal repeated telemetry payload",
        "value": i % 7,
    }
    for i in range(1000)
]
needle = "special_error_0x99"
rows.append(
    {
        "id": 99999,
        "status": "error",
        "message": f"{needle} root cause disk full",
        "value": 999.99,
    }
)

router = ContentRouter(
    ContentRouterConfig(
        smart_crusher_max_items_after_crush=8,
        smart_crusher_with_compaction=False,
    )
)

result = router.compress(json.dumps(rows), question=f"Find {needle}")
before = len(result.original.split())
after = len(result.compressed.split())

print("Strategy used:", result.strategy_used.value)
print("Before tokens:", before)
print("After tokens:", after)
print("Has CCR:", "<<ccr:" in result.compressed)
print("Transforms:", result.routing_log)
