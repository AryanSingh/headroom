import json

from cutctx.config import CCRConfig
from cutctx.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig

rows = [
    {"id": i, "status": "ok", "message": "all good", "value": i * 1.5}
    for i in range(100)
]
needle = "special_error_0x99"
rows[42]["message"] = needle

config = SmartCrusherConfig(max_items_after_crush=8)
ccr = CCRConfig(enabled=True, inject_retrieval_marker=True)
crusher = SmartCrusher(config=config, ccr_config=ccr, with_compaction=False)

res = crusher.crush(json.dumps(rows), query=f"Find {needle}")
print("Was modified:", res.was_modified)
print("Strategy:", res.strategy)
print("Length before:", len(json.dumps(rows)))
print("Length after:", len(res.compressed))
print("Has CCR:", "<<ccr:" in res.compressed)
