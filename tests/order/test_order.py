"""Tests for the Order Service using a mock Catalog Service."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Use a separate temporary database so tests never modify orders.db.
TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["ORDER_DB_PATH"] = os.path.join(
    TEMP_DIR.name, "orders-test.db"
)

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "order")
    )
)

import app as order_app
from database import get_connection


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.data = data

    def json(self):
        return self.data


class OrderServiceTests(unittest.TestCase):

    def setUp(self):
        self.client = order_app.app.test_client()

        with get_connection() as connection:
            connection.execute("DELETE FROM orders")

        self.book = {
            "id": 2,
            "title": "RPCs for Noobs.",
            "topic": "distributed systems",
            "quantity": 1,
            "price": 50.00
        }

        self.updated_book = {
            **self.book,
            "quantity": 0,
            "price": 50.00
        }

    def order_count(self):
        with get_connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM orders"
            ).fetchone()[0]

    def mock_catalog(self, mode="success"):
        def fake_request(method, url, **kwargs):

            if mode == "timeout":
                raise order_app.requests.Timeout()

            if mode == "unavailable":
                raise order_app.requests.ConnectionError()

            if url.endswith("/info/2"):
                if mode == "not_found":
                    return FakeResponse(404, {
                        "error": {
                            "code": "BOOK_NOT_FOUND",
                            "message": "Book not found"
                        }
                    })

                if mode == "invalid_response":
                    return FakeResponse(200, None)

                if mode == "out_of_stock":
                    return FakeResponse(200, {
                        **self.book,
                        "quantity": 0
                    })

                return FakeResponse(200, self.book)

            if url.endswith("/update/2"):
                if mode == "stock_race":
                    return FakeResponse(409, {
                        "error": {
                            "code": "OUT_OF_STOCK",
                            "message": "Book is out of stock"
                        }
                    })

                return FakeResponse(200, self.updated_book)

            return FakeResponse(500, {})

        return fake_request

    def test_successful_purchase(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog()
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.order_count(), 1)
        self.assertEqual(response.json["order"]["item_id"], 2)
        self.assertEqual(response.json["order"]["quantity"], 1)

    def test_out_of_stock(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("out_of_stock")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.order_count(), 0)

    def test_invalid_item_id(self):
        response = self.client.post("/purchase/abc")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.order_count(), 0)

    def test_book_not_found(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("not_found")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.order_count(), 0)

    def test_invalid_catalog_response(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("invalid_response")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.order_count(), 0)

    def test_stock_update_conflict(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("stock_race")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.order_count(), 0)

    def test_catalog_timeout(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("timeout")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(self.order_count(), 0)

    def test_catalog_unavailable(self):
        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog("unavailable")
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.order_count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
