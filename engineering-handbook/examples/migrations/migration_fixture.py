"""Deterministic offline evidence for a resumable Product Atlas schema migration."""

from __future__ import annotations


def expand(rows: list[dict[str, str]]) -> None:
    for row in rows:
        row.setdefault("display_name", "")


def backfill(rows: list[dict[str, str]], checkpoint: str | None = None) -> str:
    last = checkpoint or ""
    for row in sorted(rows, key=lambda item: item["id"]):
        if row["id"] <= last:
            continue
        if row["tenant"] == "atlas-a":
            row["display_name"] = row["given_name"] + " " + row["family_name"]
        last = row["id"]
        if last == "002" and checkpoint is None:
            raise RuntimeError("simulated worker interruption")
    return last


def contract(rows: list[dict[str, str]]) -> None:
    for row in rows:
        if row["tenant"] == "atlas-a" and not row["display_name"]:
            raise AssertionError("Atlas tenant backfill incomplete")
        if row["tenant"] == "atlas-b" and row["display_name"]:
            raise AssertionError("cross-tenant mutation detected")


def main() -> None:
    rows = [
        {"id": "001", "tenant": "atlas-a", "given_name": "Ari", "family_name": "Singh"},
        {"id": "002", "tenant": "atlas-a", "given_name": "Mina", "family_name": "Chen"},
        {"id": "003", "tenant": "atlas-b", "given_name": "Sam", "family_name": "Jones"},
    ]
    expand(rows)
    try:
        backfill(rows)
    except RuntimeError as error:
        assert str(error) == "simulated worker interruption"
    checkpoint = backfill(rows, checkpoint="002")
    assert checkpoint == "003"
    contract(rows)
    before = [row.copy() for row in rows]
    backfill(rows, checkpoint="003")
    assert rows == before
    print("MIGRATION_FIXTURE_PASS expand-compatible resumed-once tenant-isolated contract-safe")


if __name__ == "__main__":
    main()
