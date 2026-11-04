"""Order Service for Bazar.com."""

import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from database import get_connection, init_db


app = Flask(__name__)

CATALOG_URL = os.environ.get(
    "CATALOG_URL",
    "http://localhost:5001"
).rstrip("/")

TIMEOUT = 5

init_db()


def error_response(code, message, status):
    return jsonify({
        "error": {
            "code": code,
            "message": message
        }
    }), status


def validate_item_id(item_id):
    if not re.fullmatch(r"[0-9]+", item_id):
        return None

    if len(item_id) > 19:
        return None

    number = int(item_id)

    if number <= 0 or number > 9223372036854775807:
        return None

    return number


def upstream_error(response):
    """Preserve a valid business error returned by Catalog."""

    try:
        body = response.json()
    except ValueError:
        return None

    if (
        isinstance(body, dict)
        and isinstance(body.get("error"), dict)
        and isinstance(body["error"].get("code"), str)
        and isinstance(body["error"].get("message"), str)
    ):
        return jsonify(body), response.status_code

    return None


def call_catalog(method, path, **kwargs):
    """Call Catalog and translate network errors into API errors."""

    try:
        response = requests.request(
            method,
            f"{CATALOG_URL}{path}",
            timeout=TIMEOUT,
            **kwargs
        )
        return response, None

    except requests.Timeout:
        return None, error_response(
            "UPSTREAM_TIMEOUT",
            "Catalog service timed out.",
            504
        )

    except requests.RequestException:
        return None, error_response(
            "SERVICE_UNAVAILABLE",
            "Catalog service is unavailable.",
            503
        )


def valid_book(data, expected_id):
    """Check that Catalog returned the expected book information."""

    if not isinstance(data, dict):
        return False

    if type(data.get("id")) is not int or data["id"] != expected_id:
        return False

    if not isinstance(data.get("title"), str) or not data["title"]:
        return False

    if not isinstance(data.get("topic"), str):
        return False

    if type(data.get("quantity")) is not int or data["quantity"] < 0:
        return False

    price = data.get("price")

    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return False

    try:
        decimal_price = Decimal(str(price))
    except InvalidOperation:
        return False

    if not decimal_price.is_finite() or decimal_price < 0:
        return False

    cents = decimal_price * 100

    if cents != cents.to_integral_value():
        return False

    return True


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "order"
    })


@app.post("/purchase/<item_id>")
def purchase(item_id):

    book_id = validate_item_id(item_id)

    if book_id is None:
        return error_response(
            "INVALID_REQUEST",
            "Item id must be a positive integer.",
            400
        )

    # Step 1: Get book information from Catalog.
    response, error = call_catalog(
        "GET",
        f"/info/{book_id}"
    )

    if error:
        return error

    if response.status_code != 200:
        return upstream_error(response) or error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned an invalid response.",
            502
        )

    try:
        book = response.json()
    except ValueError:
        return error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned invalid JSON.",
            502
        )

    if not valid_book(book, book_id):
        return error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned invalid book information.",
            502
        )

    # Step 2: Check the available stock.
    if book["quantity"] == 0:
        return error_response(
            "OUT_OF_STOCK",
            "This book is out of stock.",
            409
        )

    # Step 3: Ask Catalog to decrease stock by one.
    response, error = call_catalog(
        "PATCH",
        f"/update/{book_id}",
        json={"quantity_delta": -1}
    )

    if error:
        return error

    if response.status_code != 200:
        return upstream_error(response) or error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned an invalid update response.",
            502
        )

    try:
        updated_book = response.json()
    except ValueError:
        return error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned invalid JSON.",
            502
        )

    if not valid_book(updated_book, book_id):
        return error_response(
            "INVALID_UPSTREAM_RESPONSE",
            "Catalog returned invalid updated book information.",
            502
        )

    # Step 4: Use the price returned by the successful update.
    price_cents = int(
        Decimal(str(updated_book["price"])) * 100
    )

    created_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    # Step 5: Save the order only after Catalog confirms the update.
    try:
        with closing(get_connection()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO orders
                        (item_id, title, quantity, price_cents, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        updated_book["title"],
                        1,
                        price_cents,
                        created_at
                    )
                )

                order_id = cursor.lastrowid

    except sqlite3.OperationalError:
        app.logger.exception("Database operation failed.")
        return error_response(
            "SERVICE_UNAVAILABLE",
            "Order database is temporarily unavailable.",
            503
        )

    except sqlite3.DatabaseError:
        app.logger.exception("Order database error.")
        return error_response(
            "INTERNAL_ERROR",
            "Could not save the order.",
            500
        )

    # Step 6: Print only after the database transaction has committed.
    print(
        f"bought book {updated_book['title']}",
        flush=True
    )

    return jsonify({
        "message": f"bought book {updated_book['title']}",
        "order": {
            "order_id": order_id,
            "item_id": book_id,
            "title": updated_book["title"],
            "quantity": 1,
            "price": price_cents / 100,
            "created_at": created_at
        }
    }), 201


@app.errorhandler(HTTPException)
def handle_http_error(error):
    codes = {
        400: "INVALID_REQUEST",
        404: "ROUTE_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        415: "UNSUPPORTED_MEDIA_TYPE"
    }

    return error_response(
        codes.get(error.code, "INTERNAL_ERROR"),
        error.description,
        error.code
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002,
        threaded=True
    )
