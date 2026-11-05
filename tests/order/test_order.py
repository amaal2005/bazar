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


    def test_updated_price_is_saved(self):
        self.updated_book["price"] = 47.25

        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog()
        ):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["order"]["price"], 47.25)

        with get_connection() as connection:
            row = connection.execute(
                "SELECT price_cents FROM orders"
            ).fetchone()

        self.assertEqual(row["price_cents"], 4725)

    def test_success_message_is_printed_after_commit(self):
        def check_committed_order(*args, **kwargs):
            # A separate connection must see the saved order at print time.
            self.assertEqual(self.order_count(), 1)

        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog()
        ), patch(
            "app.print", create=True, side_effect=check_committed_order
        ) as printed:
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 201)
        printed.assert_called_once_with(
            "bought book RPCs for Noobs.", flush=True
        )

    def test_invalid_upstream_error_status_returns_502(self):
        fake = FakeResponse(418, {
            "error": {
                "code": "BOOK_NOT_FOUND",
                "message": "Unexpected status"
            }
        })

        with patch("app.requests.request", return_value=fake):
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json["error"]["code"],
            "INVALID_UPSTREAM_RESPONSE"
        )
        self.assertEqual(self.order_count(), 0)

    def test_internal_database_error_returns_500(self):
        error = order_app.sqlite3.OperationalError("no such table: orders")
        error.sqlite_errorcode = order_app.sqlite3.SQLITE_ERROR

        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog()
        ), patch(
            "app.get_connection", side_effect=error
        ), patch.object(order_app, "print", create=True) as printed:
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json["error"]["code"], "INTERNAL_ERROR"
        )
        self.assertEqual(self.order_count(), 0)
        printed.assert_not_called()

    def test_busy_database_returns_503(self):
        error = order_app.sqlite3.OperationalError("database is locked")
        error.sqlite_errorcode = order_app.sqlite3.SQLITE_BUSY

        with patch(
            "app.requests.request",
            side_effect=self.mock_catalog()
        ), patch(
            "app.get_connection", side_effect=error
        ), patch.object(order_app, "print", create=True) as printed:
            response = self.client.post("/purchase/2")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json["error"]["code"], "SERVICE_UNAVAILABLE"
        )
        self.assertEqual(self.order_count(), 0)
        printed.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
