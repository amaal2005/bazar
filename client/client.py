"""Command-line client for the Bazar.com Frontend."""

import argparse
import json
import os
import sys
from urllib.parse import quote

import requests


def main():
    parser = argparse.ArgumentParser(description="Bazar.com bookstore client")
    parser.add_argument(
        "--url",
        default=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
        help="Frontend base URL",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="Search books by topic")
    search.add_argument("topic")

    info = commands.add_parser("info", help="Show book details")
    info.add_argument("item_id", type=int)

    purchase = commands.add_parser("purchase", help="Purchase one copy")
    purchase.add_argument("item_id", type=int)

    args = parser.parse_args()

    if args.command == "search":
        path = f"/search/{quote(args.topic, safe='')}"
    else:
        if args.item_id <= 0:
            parser.error("item_id must be a positive integer")
        path = f"/{args.command}/{args.item_id}"

    method = "POST" if args.command == "purchase" else "GET"

    try:
        # Purchases are never automatically retried.
        response = requests.request(
            method,
            f"{args.url.rstrip('/')}{path}",
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as error:
        print(f"Request failed: {error}", file=sys.stderr)
        if args.command == "purchase":
            print(
                "Purchase outcome may be unknown. Do not retry blindly.",
                file=sys.stderr,
            )
        return 1

    print(f"{method} {path} -> HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        print("Server returned invalid JSON.", file=sys.stderr)
        return 1

    expected_status = 201 if args.command == "purchase" else 200
    if response.status_code != expected_status:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 1

    if args.command == "search":
        if not data:
            print("No books found.")
        for book in data:
            print(f"{book['id']}: {book['title']}")

    elif args.command == "info":
        print(f"Book:     {data['title']}")
        print(f"Item ID:  {data['id']}")
        print(f"Topic:    {data['topic']}")
        print(f"In stock: {data['quantity']}")
        print(f"Price:    {data['price']:.2f}")

    else:
        print(data["message"])
        order = data["order"]
        print(f"Order ID: {order['order_id']}")
        print(f"Price:    {order['price']:.2f}")
        print(f"Time:     {order['created_at']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
