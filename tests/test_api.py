"""Basic API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns correct response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "qsearch"
    assert data["status"] == "running"


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_health_endpoint():
    """Test API v1 health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "qsearch-api"


def test_ingest_url_validation():
    """Test URL ingestion endpoint with invalid URL."""
    response = client.post(
        "/api/v1/ingest/url",
        json={"url": "not-a-valid-url"}
    )
    assert response.status_code == 422  # Validation error


def test_search_empty_query():
    """Test search endpoint rejects empty query."""
    response = client.post(
        "/api/v1/search",
        json={"query": ""}
    )
    assert response.status_code == 422  # Validation error


def test_search_with_valid_query():
    """Test search endpoint accepts valid query."""
    response = client.post(
        "/api/v1/search",
        json={
            "query": "test query",
            "limit": 5
        }
    )
    # Should succeed even if no documents are indexed
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert data["query"] == "test query"
