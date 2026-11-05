# Bazar.com — Distributed Bookstore

Distributed and Operating Systems — Fall 2026 — Lab 1.

A four-book online store built with Python, Flask, SQLite, and
HTTP REST microservices.

## Architecture

| Service | Role | Port |
|---|---|---|
| Frontend | Receives client requests and forwards them to backend services | 5000 |
| Catalog | Owns book information, prices, and inventory | 5001 |
| Order | Processes purchases and persists successful orders | 5002 |

Search and information requests follow:
Client → Frontend → Catalog.

Purchase requests follow:
Client → Frontend → Order → Catalog.
Order records the purchase after Catalog confirms the stock decrement.

Each service runs in a separate Linux container.
Backend services own separate SQLite databases and communicate over HTTP.

## Requirements

- Docker Engine and Docker Compose.
- Python 3.12 with venv for the host client and tests.
- On Windows: Docker Desktop with WSL 2 integration.

## Start the System

Run from the repository root:

```bash
docker compose up -d --build
docker compose ps
```

Allow a few seconds for services to initialize, then check:

```bash
curl -i http://localhost:5000/health
curl -i http://localhost:5001/health
curl -i http://localhost:5002/health
```

Frontend is available at http://localhost:5000.

## Host Client

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r client/requirements.txt
```

Search and show book details:

```bash
python client/client.py search "distributed systems"
python client/client.py info 2
```

Purchase one copy:

```bash
python client/client.py purchase 2
```

A successful purchase prints bought book followed by the book title.
Each purchase command creates a real order and decreases stock.

Use --url before the command, or set FRONTEND_URL, to select
another Frontend address:

```bash
python client/client.py --url http://localhost:5000 info 2
```

## REST Examples

```bash
curl -i "http://localhost:5000/search/distributed%20systems"
curl -i http://localhost:5000/info/2
curl -i -X POST http://localhost:5000/purchase/2
```

Catalog also exposes inventory and price updates:

```bash
curl -i -X PATCH http://localhost:5001/update/2 \
  -H "Content-Type: application/json" \
  -d '{"quantity_delta":5}'
```

The purchase and update examples change persistent data.
See [API contract](docs/api-contract.md) for request and response schemas.

## Persistence and Logs

Catalog stores /data/catalog.db in catalog_data.
Order stores /data/orders.db in order_data.
Frontend is stateless.

```bash
docker compose logs catalog order frontend
docker compose down
```

Stopping and removing containers preserves the named volumes.
docker compose down -v deletes persistent data.

The default local databases used outside Docker are separate from
the databases in Docker volumes.

## Tests

With the services running:

```bash
source .venv/bin/activate
python -m pip install requests pytest
python -m pytest tests/catalog -v
python -m pytest tests/order/test_order.py -v
python -m pytest tests/frontend/test_gateway.py -v
```

Verified results:
- Catalog: 21 passing HTTP integration tests.
- Order: 13 passing tests using a mock Catalog and temporary database.
- Frontend: 14 passing tests using mocked backend requests.

Catalog update tests temporarily modify book 2 and restore its state.
Run them on a dedicated test instance without other writers.
Do not run inventory-modifying tests in parallel.

The full-system concurrency check requires running Compose services,
available stock for book 2, and no other writers:

```bash
python scripts/check_purchase_concurrency.py
```

It sends ten purchases through Frontend with one available copy.
Expected: one 201, nine 409 responses, and exactly one new order.
It retains that real sale when removing its temporary stock adjustment.
Do not rerun blindly after a timeout or uncertain failure.

## Design and Limitations

Catalog uses atomic SQLite transactions to prevent negative inventory.
Prices are stored as integer minor units.
Databases use WAL mode, separate request connections, and lock timeouts.
SQL values use bound parameters.

Catalog and Order do not share a distributed transaction.
A failure after decrementing stock but before saving an order can leave
inventory and the order log inconsistent. A lost response can leave
the client uncertain whether a purchase completed.
Purchases are not automatically retried and are not idempotent.

The lab uses Flask's development server. Production deployment would
require a production server and additional security and recovery work.

## Evidence and Documentation

- [Catalog guide](docs/catalog-guide.md)
- [Order guide](docs/order-guide.md)
- [Client output](docs/client-output.txt)
- [Full-system logs](docs/full-system-logs.txt)
- [Full-system concurrency result](docs/full-system-concurrency.txt)
- [Catalog query tests](docs/catalog-query-tests.txt)
- [Catalog update tests](docs/catalog-update-tests.txt)
- [Order review tests](docs/order-review-tests.txt)
- [Frontend tests](docs/frontend-tests.txt)

Screenshots are stored in docs/screenshots/.
Earlier guides and captured outputs may describe an intermediate stage;
this README describes the current three-service setup.
