import time
from headroom.telemetry.episodes import EpisodeStore, CompressionEpisode
store = EpisodeStore(db_path=":memory:")
store._init_db()
ep = CompressionEpisode(
    episode_id="test1",
    tenant_id="t1",
    original_size=100,
    compressed_size=50,
    start_line=0,
    end_line=10,
    timestamp_ts=time.time()
)
store.record_compression(ep)
print("First insert ok")
store.record_compression(ep)
print("Second insert ok")
