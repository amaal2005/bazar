"""HTTP tests for atomic Catalog updates.

Run against a dedicated test instance without other writers.
"""

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import requests

BASE = os.environ.get(
    "CATALOG_URL", "http://localhost:5001"
).rstrip("/")


def get_book():
    response = requests.get(f"{BASE}/info/2", timeout=10)
    response.raise_for_status()
    return response.json()


def patch(data, item_id=2):
    return requests.patch(
        f"{BASE}/update/{item_id}",
        json=data,
        timeout=15,
    )


@pytest.fixture
def original_book():
    """Restore the original quantity and price after each test."""
    original = get_book()
    try:
        yield original
    finally:
        current = get_book()
        changes = {"price": original["price"]}
        delta = original["quantity"] - current["quantity"]
        if delta:
            changes["quantity_delta"] = delta
        response = patch(changes)
        response.raise_for_status()
        assert get_book() == original


def test_restock_and_price_update(original_book):
    response = patch({"quantity_delta": 3, "price": 42.50})
    assert response.status_code == 200
    book = response.json()
    assert book["quantity"] == original_book["quantity"] + 3
    assert book["price"] == 42.50
    assert get_book() == book


def test_failed_update_changes_nothing(original_book):
    response = patch({
        "quantity_delta": -(original_book["quantity"] + 1),
        "price": 1,
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUT_OF_STOCK"
    assert get_book() == original_book


@pytest.mark.parametrize("data", [
    {"price": -1},
    {"price": True},
    {"price": 1.234},
    {"quantity_delta": 1.5},
    {"quantity_delta": True},
    {"quantity_delta": 0},
    {},
    {"stock": 5},
])
def test_invalid_input(data, original_book):
    response = patch(data)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert get_book() == original_book


def test_missing_book():
    response = patch({"quantity_delta": -1}, item_id=999)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


def test_wrong_content_type(original_book):
    response = requests.patch(
        f"{BASE}/update/2",
        data='{"price":20}',
        headers={"Content-Type": "text/plain"},
        timeout=10,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert get_book() == original_book


def test_concurrent_last_copy(original_book):
    delta = 1 - original_book["quantity"]
    if delta:
        response = patch({"quantity_delta": delta})
        response.raise_for_status()

    assert get_book()["quantity"] == 1
    barrier = Barrier(10)

    def decrement(_):
        barrier.wait(timeout=15)
        response = patch({"quantity_delta": -1})
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(decrement, range(10)))

    counts = Counter(status for status, _ in results)
    assert counts == {200: 1, 409: 9}, results

    for status, body in results:
        if status == 200:
            assert body["quantity"] == 0
            assert body["price"] == original_book["price"]
        else:
            assert body["error"]["code"] == "OUT_OF_STOCK"

    assert get_book()["quantity"] == 0
