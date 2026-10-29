"""Catalog REST API for Bazar.com."""

from contextlib import closing

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from database import get_connection, init_db
from update_routes import register_update_routes

app = Flask(__name__)
init_db()
register_update_routes(app)


def error_response(code, message, status):
    """Return errors using the shared API contract."""
    return jsonify({
        "error": {
            "code": code,
            "message": message,
        }
    }), status


@app.get("/health")
def health():
    """Report that the catalog service is running."""
    return jsonify({"status": "ok", "service": "catalog"})


@app.get("/search/<topic>")
def search(topic):
    """Return book ids and titles matching a topic."""
    normalized_topic = topic.strip().lower()

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, title
            FROM books
            WHERE topic = ? COLLATE NOCASE
            ORDER BY id
            """,
            (normalized_topic,),
        ).fetchall()

    return jsonify([dict(row) for row in rows])


@app.get("/info/<item_id>")
def info(item_id):
    """Return the complete details of one book."""
    if (
        not item_id.isascii()
        or not item_id.isdecimal()
        or len(item_id) > 19
    ):
        return error_response(
            "INVALID_REQUEST", "Item id must be a positive integer.", 400
        )

    book_id = int(item_id)

    if book_id <= 0:
        return error_response(
            "INVALID_REQUEST", "Item id must be a positive integer.", 400
        )

    # SQLite integer identifiers are signed 64-bit values.
    if book_id > 9223372036854775807:
        return error_response(
            "BOOK_NOT_FOUND", "Book does not exist.", 404
        )

    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, title, topic, quantity, price_cents
            FROM books
            WHERE id = ?
            """,
            (book_id,),
        ).fetchone()

    if row is None:
        return error_response(
            "BOOK_NOT_FOUND", "Book does not exist.", 404
        )

    book = dict(row)
    book["price"] = book.pop("price_cents") / 100
    return jsonify(book)


@app.errorhandler(HTTPException)
def handle_http_error(error):
    """Keep route and method errors in JSON format."""
    codes = {
        400: "INVALID_REQUEST",
        404: "ROUTE_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        415: "UNSUPPORTED_MEDIA_TYPE",
    }
    return error_response(
        codes.get(error.code, "INTERNAL_ERROR"),
        error.description,
        error.code,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, threaded=True)
