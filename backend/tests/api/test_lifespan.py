from fastapi.testclient import TestClient

from app.db import connection
from app.main import app


def test_lifespan_wires_state_and_shuts_down_cleanly(tmp_path, monkeypatch):
    """Entering the context runs the lifespan handler (init_db, provider,
    background tasks); leaving it cancels the tasks."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "lifespan.db")

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert app.state.price_cache is not None
        assert app.state.provider.is_supported("AAPL")

