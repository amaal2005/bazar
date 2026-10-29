"""Catalog microservice for Bazar.com."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    """Report that the catalog service is running."""
    return jsonify({"status": "ok", "service": "catalog"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, threaded=True)
