import threading
import time
import pytest
import uvicorn
from app.main import app
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def run_test_fixture_server():
    """
    Session-scoped background uvicorn server so Playwright tests
    can reliably hit http://127.0.0.1:8000/fixture/product without manual setup.
    """
    settings.TEST_MODE = True
    config = uvicorn.Config(app, host="127.0.0.1", port=settings.API_PORT, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.2)
    yield
    server.should_exit = True
