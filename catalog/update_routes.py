"""Atomic catalog updates."""

import sqlite3
from contextlib import closing
from decimal import Decimal, InvalidOperation

from flask import jsonify, request

from database import get_connection


def register_update_routes(app):
    """Register the inventory and price update endpoint."""

    def fail(code, message, status):
        return jsonify({
            "error": {"code": code, "message": message}
        }), status

    @app.patch("/update/<item_id>")
    def update(item_id):
        """Validate and apply all requested changes atomically."""
        if (
            not item_id.isascii()
            or not item_id.isdecimal()
            or len(item_id) > 19
            or int(item_id) <= 0
        ):
            return fail("INVALID_REQUEST", "Invalid item id.", 400)

        book_id = int(item_id)
        if book_id > 9223372036854775807:
            return fail("BOOK_NOT_FOUND", "Book does not exist.", 404)

        if not request.is_json:
            return fail(
                "UNSUPPORTED_MEDIA_TYPE",
                "Content-Type must be application/json.",
                415,
            )

        data = request.get_json()

        if (
            not isinstance(data, dict)
            or not data
            or set(data) - {"quantity_delta", "price"}
        ):
            return fail("INVALID_REQUEST", "Invalid update fields.", 400)

        delta = data.get("quantity_delta", 0)
        if "quantity_delta" in data:
            if (
                type(delta) is not int
                or delta == 0
                or abs(delta) > 9223372036854775807
            ):
                return fail(
                    "INVALID_REQUEST",
                    "quantity_delta must be a nonzero supported integer.",
                    400,
                )

        price_cents = None
        if "price" in data:
            if type(data["price"]) not in (int, float):
                return fail("INVALID_REQUEST", "Invalid price.", 400)

            try:
                price = Decimal(str(data["price"]))
                cents = price * 100
                if (
                    not price.is_finite()
                    or price < 0
                    or cents != cents.to_integral_value()
                    or cents > 9223372036854775807
                ):
                    raise ValueError
                price_cents = int(cents)
            except (InvalidOperation, ValueError, OverflowError):
                return fail("INVALID_REQUEST", "Invalid price.", 400)

        try:
            with closing(get_connection()) as connection:
                # The context commits on success and rolls back on failure.
                with connection:
                    connection.execute("BEGIN IMMEDIATE")

                    current = connection.execute(
                        "SELECT * FROM books WHERE id = ?",
                        (book_id,),
                    ).fetchone()

                    if current is None:
                        return fail(
                            "BOOK_NOT_FOUND", "Book does not exist.", 404
                        )

                    quantity = current["quantity"] + delta

                    if quantity < 0:
                        return fail(
                            "OUT_OF_STOCK", "Book is out of stock.", 409
                        )

                    if quantity > 9223372036854775807:
                        return fail(
                            "INVALID_REQUEST", "Quantity is too large.", 400
                        )

                    new_price = (
                        current["price_cents"]
                        if price_cents is None
                        else price_cents
                    )

                    connection.execute(
                        """
                        UPDATE books
                        SET quantity = ?, price_cents = ?
                        WHERE id = ?
                        """,
                        (quantity, new_price, book_id),
                    )

                    # Read the purchase price before committing.
                    updated = connection.execute(
                        "SELECT * FROM books WHERE id = ?",
                        (book_id,),
                    ).fetchone()
                    book = dict(updated)
                    book["price"] = book.pop("price_cents") / 100

                # Only return success after COMMIT completes.
                return jsonify(book)

        except sqlite3.OperationalError as error:
            app.logger.exception("Catalog update failed")
            if getattr(error, "sqlite_errorcode", None) in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            ):
                return fail(
                    "SERVICE_UNAVAILABLE", "Database is busy.", 503
                )
            return fail("INTERNAL_ERROR", "Catalog update failed.", 500)

        except sqlite3.DatabaseError:
            app.logger.exception("Catalog database failure")
            return fail("INTERNAL_ERROR", "Catalog update failed.", 500)
