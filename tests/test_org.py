"""Tests for the org/workspace/project data model (headroom/org.py)."""

from __future__ import annotations

import pytest

from headroom.org import OrgStore, get_org_store, reset_org_store


@pytest.fixture
def org_store(tmp_path):
    """Create an org store with a temp DB."""
    db_path = tmp_path / "test_org.db"
    store = OrgStore(db_path=str(db_path))
    yield store
    store.close()


class TestOrganization:
    """Tests for organization CRUD."""

    def test_create_org(self, org_store):
        org = org_store.create_org(name="Acme Corp", admin_email="admin@acme.com")
        assert org["name"] == "Acme Corp"
        assert org["admin_email"] == "admin@acme.com"
        assert org["id"] is not None
        assert len(org["id"]) == 16

    def test_get_org(self, org_store):
        org = org_store.create_org(name="Test Org")
        fetched = org_store.get_org(org["id"])
        assert fetched is not None
        assert fetched["name"] == "Test Org"

    def test_get_nonexistent_org(self, org_store):
        assert org_store.get_org("nonexistent") is None

    def test_list_orgs(self, org_store):
        org_store.create_org(name="Org A")
        org_store.create_org(name="Org B")
        orgs = org_store.list_orgs()
        assert len(orgs) == 2

    def test_update_org(self, org_store):
        org = org_store.create_org(name="Old Name")
        updated = org_store.update_org(org["id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_update_org_settings(self, org_store):
        org = org_store.create_org(name="Test", settings={"theme": "dark"})
        updated = org_store.update_org(org["id"], settings={"theme": "light"})
        assert updated["settings"]["theme"] == "light"

    def test_delete_org_cascade(self, org_store):
        org = org_store.create_org(name="To Delete")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        org_store.create_agent(project_id=proj["id"], name="Agent")

        assert org_store.delete_org(org["id"]) is True
        assert org_store.get_org(org["id"]) is None
        assert org_store.get_workspace(ws["id"]) is None
        assert org_store.get_project(proj["id"]) is None

    def test_org_slug_auto_generated(self, org_store):
        org = org_store.create_org(name="My Organization")
        assert org["slug"] == "my-organization"


class TestWorkspace:
    """Tests for workspace CRUD."""

    def test_create_workspace(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="Engineering")
        assert ws["name"] == "Engineering"
        assert ws["org_id"] == org["id"]

    def test_list_workspaces(self, org_store):
        org = org_store.create_org(name="Org")
        org_store.create_workspace(org_id=org["id"], name="WS A")
        org_store.create_workspace(org_id=org["id"], name="WS B")
        workspaces = org_store.list_workspaces(org["id"])
        assert len(workspaces) == 2

    def test_update_workspace(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="Old")
        updated = org_store.update_workspace(ws["id"], name="New")
        assert updated["name"] == "New"

    def test_delete_workspace_cascade(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        org_store.create_agent(project_id=proj["id"], name="Agent")

        assert org_store.delete_workspace(ws["id"]) is True
        assert org_store.get_workspace(ws["id"]) is None
        assert org_store.get_project(proj["id"]) is None

    def test_workspace_slug_auto_generated(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="Backend Team")
        assert ws["slug"] == "backend-team"


class TestProject:
    """Tests for project CRUD."""

    def test_create_project(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="backend-api", path="/src/backend")
        assert proj["name"] == "backend-api"
        assert proj["path"] == "/src/backend"
        assert proj["workspace_id"] == ws["id"]

    def test_list_projects(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        org_store.create_project(workspace_id=ws["id"], name="P1")
        org_store.create_project(workspace_id=ws["id"], name="P2")
        projects = org_store.list_projects(ws["id"])
        assert len(projects) == 2

    def test_update_project(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Old")
        updated = org_store.update_project(proj["id"], name="New", path="/new/path")
        assert updated["name"] == "New"
        assert updated["path"] == "/new/path"

    def test_delete_project_cascade(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        org_store.create_agent(project_id=proj["id"], name="Agent")

        assert org_store.delete_project(proj["id"]) is True
        assert org_store.get_project(proj["id"]) is None

    def test_find_project_by_path(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        org_store.create_project(workspace_id=ws["id"], name="Proj", path="/unique/path")
        found = org_store.find_project_by_path("/unique/path")
        assert found is not None
        assert found["name"] == "Proj"


class TestAgent:
    """Tests for agent CRUD."""

    def test_create_agent(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        agent = org_store.create_agent(project_id=proj["id"], name="claude-code", agent_type="coding")
        assert agent["name"] == "claude-code"
        assert agent["agent_type"] == "coding"

    def test_list_agents(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        org_store.create_agent(project_id=proj["id"], name="A1")
        org_store.create_agent(project_id=proj["id"], name="A2")
        agents = org_store.list_agents(proj["id"])
        assert len(agents) == 2

    def test_delete_agent(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        agent = org_store.create_agent(project_id=proj["id"], name="Agent")
        assert org_store.delete_agent(agent["id"]) is True
        assert org_store.get_agent(agent["id"]) is None


class TestHierarchy:
    """Tests for hierarchy lookups."""

    def test_get_org_hierarchy(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS")
        proj = org_store.create_project(workspace_id=ws["id"], name="Proj")
        org_store.create_agent(project_id=proj["id"], name="Agent")

        hierarchy = org_store.get_org_hierarchy(org["id"])
        assert hierarchy is not None
        assert hierarchy["name"] == "Org"
        assert len(hierarchy["workspaces"]) == 1
        assert len(hierarchy["workspaces"][0]["projects"]) == 1
        assert len(hierarchy["workspaces"][0]["projects"][0]["agents"]) == 1

    def test_resolve_project(self, org_store):
        org = org_store.create_org(name="Acme")
        ws = org_store.create_workspace(org_id=org["id"], name="Eng")
        proj = org_store.create_project(workspace_id=ws["id"], name="API")

        resolved = org_store.resolve_project(proj["id"])
        assert resolved is not None
        assert resolved["project"]["name"] == "API"
        assert resolved["workspace"]["name"] == "Eng"
        assert resolved["organization"]["name"] == "Acme"

    def test_resolve_nonexistent_project(self, org_store):
        assert org_store.resolve_project("nonexistent") is None

    def test_get_org_hierarchy_nonexistent(self, org_store):
        assert org_store.get_org_hierarchy("nonexistent") is None


class TestSettings:
    """Tests for JSON settings parsing."""

    def test_org_settings_parsed(self, org_store):
        org = org_store.create_org(name="Org", settings={"key": "value", "nested": {"a": 1}})
        fetched = org_store.get_org(org["id"])
        assert fetched["settings"]["key"] == "value"
        assert fetched["settings"]["nested"]["a"] == 1

    def test_workspace_settings_parsed(self, org_store):
        org = org_store.create_org(name="Org")
        ws = org_store.create_workspace(org_id=org["id"], name="WS", settings={"auto_compress": True})
        fetched = org_store.get_workspace(ws["id"])
        assert fetched["settings"]["auto_compress"] is True

    def test_default_empty_settings(self, org_store):
        org = org_store.create_org(name="Org")
        assert org["settings"] == {}


class TestGlobalSingleton:
    """Tests for the module-level singleton."""

    def setup_method(self):
        reset_org_store()

    def teardown_method(self):
        reset_org_store()

    def test_get_creates_singleton(self, tmp_path):
        store1 = get_org_store(db_path=tmp_path / "test.db")
        store2 = get_org_store(db_path=tmp_path / "test.db")
        assert store1 is store2

    def test_reset_clears_singleton(self, tmp_path):
        store1 = get_org_store(db_path=tmp_path / "test.db")
        reset_org_store()
        store2 = get_org_store(db_path=tmp_path / "test.db")
        assert store1 is not store2
