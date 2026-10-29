"""HTTP integration tests for the running Catalog service."""

import os

import requests

BASE_URL = os.environ.get(
    "CATALOG_URL", "http://localhost:5001"
).rstrip("/")


def get(path):
    """Send a request with a bounded timeout."""
    return requests.get(f"{BASE_URL}{path}", timeout=10)


def test_health():
    response = get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "catalog",
    }


def test_search_distributed_systems():
    response = get("/search/distributed%20systems")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "title": "How to get a good grade in DOS in 40 minutes a day.",
        },
        {"id": 2, "title": "RPCs for Noobs."},
    ]


def test_search_undergraduate_school():
    response = get("/search/undergraduate%20school")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 3,
            "title": "Xen and the Art of Surviving Undergraduate School.",
        },
        {"id": 4, "title": "Cooking for the Impatient Undergrad."},
    ]


def test_search_unknown_topic():
    response = get("/search/unknown")
    assert response.status_code == 200
    assert response.json() == []


def test_search_normalizes_topic():
    response = get("/search/%20DISTRIBUTED%20SYSTEMS%20")
    assert response.status_code == 200
    assert [book["id"] for book in response.json()] == [1, 2]


def test_book_info():
    response = get("/info/2")
    assert response.status_code == 200
    book = response.json()
    assert book["id"] == 2
    assert book["title"] == "RPCs for Noobs."
    assert book["topic"] == "distributed systems"
    assert type(book["quantity"]) is int
    assert book["quantity"] >= 0
    assert type(book["price"]) in (int, float)
    assert book["price"] >= 0


def test_missing_book():
    response = get("/info/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


def test_invalid_book_id():
    response = get("/info/abc")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
