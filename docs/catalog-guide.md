# Catalog Service Guide

## Scope

The Catalog service owns the four-book catalog and supports topic
search, book details, price updates, and inventory adjustments.
It uses Flask and a persistent SQLite database.

The current Compose configuration runs Catalog only.
Order and Frontend must be added before the complete lab deployment
and end-to-end purchase tests are considered finished.

## Run with Docker Compose

Requirements: Docker Engine and Docker Compose.

Run from the repository root:

```bash
docker compose up -d --build catalog
docker compose ps
curl -i http://localhost:5001/health
```

View component logs:

```bash
docker compose logs catalog
```

Stop and remove the container while retaining its database:

```bash
docker compose down
```

The named volume catalog_data stores /data/catalog.db.
Running docker compose down -v deletes the stored database.

## Run locally

Requirements: Python 3.12 and its venv module.

Do not run the local service and Docker service on port 5001
at the same time.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r catalog/requirements.txt
python catalog/app.py
```

The default local database is catalog/catalog.db.
CATALOG_DB_PATH can override its location.

Local execution and Docker use separate databases.
Initial data is inserted without resetting existing books.

## API examples

```bash
curl -i "http://localhost:5001/search/distributed%20systems"
curl -i http://localhost:5001/info/2
curl -i -X PATCH http://localhost:5001/update/2 \
  -H "Content-Type: application/json" \
  -d '{"quantity_delta":1}'
curl -i -X PATCH http://localhost:5001/update/2 \
  -H "Content-Type: application/json" \
  -d '{"price":45}'
```

See docs/api-contract.md for complete response and error schemas.

## Automated integration tests

Start Catalog before running the tests.

```bash
source .venv/bin/activate
python -m pip install requests pytest
python -m pytest tests/catalog -v
```

CATALOG_URL can select another Catalog instance.

Update tests temporarily modify book 2 and restore its original
quantity and price after each test. Run them against a dedicated
test instance with no other purchases or inventory updates.
Do not run these tests concurrently with each other.

Recorded test output:
- docs/catalog-query-tests.txt: 8 passing query tests.
- docs/catalog-update-tests.txt: 13 passing update tests.

## Storage and concurrency design

Each request uses a separate SQLite connection.
Connections wait up to five seconds for database locks.
The database uses WAL mode.

Catalog update transactions use BEGIN IMMEDIATE before checking
existence and stock. They apply changes and read the resulting book,
including its price, before committing. Success is returned only
after the commit completes.

This prevents concurrent decrements from overselling the last copy.
An update that would produce negative inventory returns 409.
A nonexistent book returns 404, including for decrement requests.
Combined price and quantity updates are applied together or rejected
without changing either field.

Prices are stored as integer minor units and exposed as JSON numbers.
SQL queries use bound parameters.

## Tradeoffs and limitations

SQLite keeps deployment small and avoids a separate database server.
It serializes writers, so it is less suitable for heavy write traffic.

The Flask development server is used for this lab; a production
deployment should use a production WSGI server.

Atomic Catalog updates do not create a distributed transaction with
Order. A crash after stock decrement but before order persistence can
leave the two services inconsistent. Purchase idempotency,
reservations, and reconciliation are possible future improvements.

The concurrency test currently targets Catalog decrements.
Full purchase concurrency and order-log consistency must also be
tested after Order and Frontend are integrated.

## Verification completed

- Search, Info, missing books, and unknown topics.
- Inventory and price updates, input validation, and rejected updates.
- Ten concurrent decrements with one copy: one success and nine conflicts.
- Local persistence after service restart.
- Docker volume persistence after container removal and recreation.

The final submission must also include the complete three-service
Compose deployment, actual client and component output, and the
combined 2–3 page design document.
