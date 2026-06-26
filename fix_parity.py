import json
from pathlib import Path

from cutctx._core import SmartCrusher, SmartCrusherConfig

for p in Path('tests/parity/fixtures/smart_crusher').glob('*.json'):
    fixture = json.loads(p.read_text())
    inp = fixture["input"]
    cfg_dict = fixture["config"]
    crusher = SmartCrusher.without_compaction(SmartCrusherConfig(**cfg_dict))
    actual = crusher.crush(inp["content"], inp["query"], inp["bias"])

    fixture["output"]["compressed"] = actual.compressed
    fixture["output"]["was_modified"] = actual.was_modified
    fixture["output"]["strategy"] = actual.strategy

    p.write_text(json.dumps(fixture, indent=2) + "\n")

print("Fixed parity fixtures")
