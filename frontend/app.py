"""Frontend HTTP gateway for Bazar.com."""

import os

import requests
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from urllib.parse import quote

app = Flask(__name__)

CATALOG_URL = os.environ.get(
    "CATALOG_URL", "http://localhost:5001"
).rstrip("/")
ORDER_URL = os.environ.get(
    "ORDER_URL", "http://localhost:5002"
).rstrip("/")


def fail(code, message, status):
    """Return a consistent JSON error."""
    return jsonify({
        "error": {"code": code, "message": message}
    }), status


def forward(method, base_url, path, success_status):
    """Forward once, preserving valid JSON responses and errors."""
    try:
        response = requests.request(
            method,
            f"{base_url}{path}",
            timeout=12,
            allow_redirects=False,
        )
    except requests.Timeout:
        return fail("UPSTREAM_TIMEOUT", "Backend request timed out.", 504)
    except requests.RequestException:
        return fail(
            "SERVICE_UNAVAILABLE", "Backend service is unavailable.", 503
        )

    try:
        body = response.json()
    except ValueError:
        return fail(
            "INVALID_UPSTREAM_RESPONSE", "Backend returned invalid JSON.", 502
        )

    if response.status_code == success_status:
        valid = (
            isinstance(body, list)
            if path.startswith("/search/")
            else isinstance(body, dict) and "error" not in body
        )
        if valid:
            return jsonify(body), response.status_code
    else:
        allowed = {
            400: {"INVALID_REQUEST"},
            404: {"BOOK_NOT_FOUND", "ROUTE_NOT_FOUND"},
            405: {"METHOD_NOT_ALLOWED"},
            409: {"OUT_OF_STOCK"},
            415: {"UNSUPPORTED_MEDIA_TYPE"},
            500: {"INTERNAL_ERROR"},
            502: {"INVALID_UPSTREAM_RESPONSE"},
            503: {"SERVICE_UNAVAILABLE"},
            504: {"UPSTREAM_TIMEOUT"},
        }
        error = body.get("error") if isinstance(body, dict) else None
        if (
            isinstance(error, dict)
            and isinstance(error.get("code"), str)
            and error["code"] in allowed.get(response.status_code, set())
            and isinstance(error.get("message"), str)
        ):
            return jsonify(body), response.status_code

    return fail(
        "INVALID_UPSTREAM_RESPONSE", "Backend returned an invalid response.", 502
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "frontend"})


@app.get("/search/<topic>")
def search(topic):
    return forward(
        "GET", CATALOG_URL, f"/search/{quote(topic, safe='')}", 200
    )


@app.get("/info/<item_id>")
def info(item_id):
    return forward(
        "GET", CATALOG_URL, f"/info/{quote(item_id, safe='')}", 200
    )


@app.post("/purchase/<item_id>")
def purchase(item_id):
    # Never retry purchases: a lost reply can hide a completed purchase.
    return forward(
        "POST", ORDER_URL, f"/purchase/{quote(item_id, safe='')}", 201
    )


@app.errorhandler(HTTPException)
def handle_http_error(error):
    codes = {
        400: "INVALID_REQUEST",
        404: "ROUTE_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        415: "UNSUPPORTED_MEDIA_TYPE",
    }
    return fail(
        codes.get(error.code, "INTERNAL_ERROR"),
        error.description,
        error.code,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
