from __future__ import annotations

from headroom.scim import ScimStore


def test_scim_store_user_crud(tmp_path):
    store = ScimStore(db_path=tmp_path / "scim.db")

    user = store.create_user(
        user_name="alice@example.com",
        display_name="Alice",
        emails=[{"value": "alice@example.com", "primary": True}],
        meta={"source": "okta"},
    )
    assert user["user_name"] == "alice@example.com"
    assert user["meta"] == {"source": "okta"}

    updated = store.update_user(
        user["id"],
        display_name="Alice Admin",
        active=False,
    )
    assert updated is not None
    assert updated["display_name"] == "Alice Admin"
    assert updated["active"] is False

    listed = store.list_users(user_name="alice@example.com")
    assert len(listed) == 1

    assert store.delete_user(user["id"]) is True
    assert store.get_user(user["id"]) is None


def test_scim_store_group_crud(tmp_path):
    store = ScimStore(db_path=tmp_path / "scim.db")

    group = store.create_group(
        display_name="Platform Admins",
        members=[{"value": "user-1"}],
        meta={"source": "entra"},
    )
    assert group["display_name"] == "Platform Admins"

    updated = store.update_group(
        group["id"],
        members=[{"value": "user-1"}, {"value": "user-2"}],
    )
    assert updated is not None
    assert len(updated["members"]) == 2

    listed = store.list_groups()
    assert len(listed) == 1

    assert store.delete_group(group["id"]) is True
    assert store.get_group(group["id"]) is None
