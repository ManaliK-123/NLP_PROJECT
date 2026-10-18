import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "provider" in data

def test_list_meetings_and_demo_seed(client):
    response = client.get("/api/meetings")
    assert response.status_code == 200
    meetings = response.json()
    assert len(meetings) >= 1
    demo = meetings[0]
    assert "title" in demo

def test_dashboard_analytics_endpoint(client):
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "radar" in data
    assert data["radar"]["health_status"] in ("Healthy", "At Risk", "Critical")

def test_evaluation_benchmark_endpoint(client):
    response = client.get("/api/evaluation/benchmark")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "rule_based" in data["models"]
    assert "hybrid_llm" in data["models"]
