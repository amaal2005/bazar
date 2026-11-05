"""Frontend gateway tests with mocked backend HTTP calls."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

# Load under a unique name to avoid colliding with Order's app module.
APP_PATH = Path(__file__).resolve().parents[2] / "frontend" / "app.py"
spec = importlib.util.spec_from_file_location("bazar_frontend", APP_PATH)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class FakeResponse:
    def __init__(self, status, body, invalid_json=False):
        self.status_code = status
        self.body = body
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("Invalid JSON")
        return self.body


@pytest.fixture
def client():
    return gateway.app.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"service": "frontend", "status": "ok"}


def test_search_forwarding(client):
    books = [{"id": 2, "title": "RPCs for Noobs."}]
    with patch.object(
        gateway.requests, "request",
        return_value=FakeResponse(200, books),
    ) as request:
        response = client.get("/search/distributed%20systems")

    assert response.status_code == 200
    assert response.json == books
    request.assert_called_once_with(
        "GET",
        gateway.CATALOG_URL + "/search/distributed%20systems",
        timeout=12,
        allow_redirects=False,
    )


def test_info_forwarding(client):
    book = {
        "id": 2, "title": "RPCs for Noobs.",
        "topic": "distributed systems", "quantity": 8, "price": 47,
    }
    with patch.object(
        gateway.requests, "request",
        return_value=FakeResponse(200, book),
    ) as request:
        response = client.get("/info/2")

    assert response.status_code == 200
    assert response.json == book
    assert request.call_args.args == (
        "GET", gateway.CATALOG_URL + "/info/2"
    )


def test_purchase_forwarded_once(client):
    body = {
        "message": "bought book RPCs for Noobs.",
        "order": {
            "order_id": 1, "item_id": 2,
            "title": "RPCs for Noobs.", "quantity": 1,
            "price": 47, "created_at": "2026-11-05T19:20:10Z",
        },
    }
    with patch.object(
        gateway.requests, "request",
        return_value=FakeResponse(201, body),
    ) as request:
        response = client.post("/purchase/2")

    assert response.status_code == 201
    assert response.json == body
    request.assert_called_once_with(
        "POST",
        gateway.ORDER_URL + "/purchase/2",
        timeout=12,
        allow_redirects=False,
    )


@pytest.mark.parametrize("status, code", [
    (404, "BOOK_NOT_FOUND"),
    (409, "OUT_OF_STOCK"),
    (503, "SERVICE_UNAVAILABLE"),
])
def test_preserves_backend_errors(client, status, code):
    body = {"error": {"code": code, "message": "Backend failure"}}
    with patch.object(
        gateway.requests, "request",
        return_value=FakeResponse(status, body),
    ):
        response = client.post("/purchase/2")

    assert response.status_code == status
    assert response.json == body


@pytest.mark.parametrize("exception, status, code", [
    (requests.Timeout(), 504, "UPSTREAM_TIMEOUT"),
    (requests.ConnectionError(), 503, "SERVICE_UNAVAILABLE"),
])
def test_network_failure_without_retry(client, exception, status, code):
    with patch.object(
        gateway.requests, "request", side_effect=exception,
    ) as request:
        response = client.post("/purchase/2")

    assert response.status_code == status
    assert response.json["error"]["code"] == code
    request.assert_called_once()


@pytest.mark.parametrize("backend", [
    FakeResponse(200, None),
    FakeResponse(200, {}, invalid_json=True),
    FakeResponse(418, {"error": {
        "code": "BOOK_NOT_FOUND", "message": "Wrong status",
    }}),
])
def test_invalid_backend_response(client, backend):
    with patch.object(
        gateway.requests, "request", return_value=backend,
    ):
        response = client.get("/info/2")

    assert response.status_code == 502
    assert response.json["error"]["code"] == "INVALID_UPSTREAM_RESPONSE"


def test_unknown_route(client):
    response = client.get("/unknown")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "ROUTE_NOT_FOUND"


def test_purchase_requires_post(client):
    response = client.get("/purchase/2")
    assert response.status_code == 405
    assert response.json["error"]["code"] == "METHOD_NOT_ALLOWED"
