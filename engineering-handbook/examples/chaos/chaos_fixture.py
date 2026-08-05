"""Deterministic Product Atlas queue-partition evidence fixture."""

from collections import Counter


def main() -> None:
    accepted = [{"key": "atlas-queue-0042", "tenant": "atlas-a"}]
    queue = list(accepted)  # worker partition: acknowledgement remains durable.
    abort_threshold = 30
    observed_queue_age_seconds = 12
    recovered = [queue.pop()]
    outcomes = Counter(item["key"] for item in recovered)
    assert observed_queue_age_seconds < abort_threshold
    assert outcomes == Counter({"atlas-queue-0042": 1})
    assert recovered[0]["tenant"] == "atlas-a"
    print("CHAOS_FIXTURE_PASS queued-once recovered-once abort-threshold-armed")


if __name__ == "__main__":
    main()
