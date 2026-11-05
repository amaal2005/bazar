"""Verify concurrent purchases through all three services.

Run on a test instance with no other writers.
This creates one real order. Do not retry after an uncertain failure.
"""

import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import requests

FRONTEND = "http://localhost:5000"
CATALOG = "http://localhost:5001"


def book():
    response = requests.get(f"{FRONTEND}/info/2", timeout=15)
    response.raise_for_status()
    return response.json()


def order_count():
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "order",
            "python", "-c",
            "from database import get_connection; "
            "c=get_connection(); "
            "print(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]); "
            "c.close()",
        ],
        check=True, capture_output=True, text=True,
    )
    return int(result.stdout.strip())


def adjust_stock(delta):
    if delta:
        response = requests.patch(
            f"{CATALOG}/update/2",
            json={"quantity_delta": delta},
            timeout=15,
        )
        response.raise_for_status()


def main():
    original = book()
    assert original["quantity"] >= 1, "At least one copy is required."
    before = order_count()

    adjust_stock(1 - original["quantity"])
    assert book()["quantity"] == 1
    barrier = Barrier(10)

    def purchase(_):
        barrier.wait(timeout=15)
        response = requests.post(
            f"{FRONTEND}/purchase/2", timeout=20
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(purchase, range(10)))

    counts = Counter(status for status, _ in results)
    after = order_count()

    print("Route: Client -> Frontend -> Order -> Catalog")
    print("Response counts:", dict(sorted(counts.items())))
    print("Final test stock:", book()["quantity"])
    print("Orders before:", before)
    print("Orders after:", after)

    assert counts == {201: 1, 409: 9}, results
    assert book()["quantity"] == 0
    assert after == before + 1

    for status, body in results:
        if status == 409:
            assert body["error"]["code"] == "OUT_OF_STOCK"
        else:
            assert body["order"]["item_id"] == 2
            assert body["order"]["quantity"] == 1
            assert body["order"]["price"] == original["price"]

    # Remove the temporary setup adjustment, retaining the real sale.
    target = original["quantity"] - 1
    adjust_stock(target)
    assert book()["quantity"] == target

    print("Stock after restoring test setup:", target)
    print("PASS: One purchase and one order; no overselling.")


if __name__ == "__main__":
    main()
