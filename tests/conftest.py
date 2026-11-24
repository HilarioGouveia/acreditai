import pytest
from fastapi.testclient import TestClient
from acreditai.api.main import app, repo
from acreditai.storage.repository import ExecucaoRepository


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_acreditai.db")
    test_repo = ExecucaoRepository(db_path=db_file)
    monkeypatch.setattr("acreditai.api.main.repo", test_repo)
    return TestClient(app)
