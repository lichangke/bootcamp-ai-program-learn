from pathlib import Path

import pytest
from app.main import app
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
