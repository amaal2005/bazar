# Bazar.com — Distributed Bookstore

Distributed and Operating Systems — Fall 2026 — Lab 1.

A small online bookstore with four books, implemented using a two-tier
architecture and three HTTP REST microservices.

## Architecture

| Service | Responsibility | Port |
|---|---|---|
| Frontend | Accept client requests and forward them to backend services | 5000 |
| Catalog | Search books, return details, and update prices and inventory | 5001 |
| Order | Process purchases and persist successful orders | 5002 |

Frontend forwards search and info requests to Catalog.
Purchase requests go to Order, which queries and updates Catalog.

Each backend service owns its persistent data. Services communicate
through HTTP rather than accessing each other's databases.

## Current Status

Catalog is implemented and tested, including:
- Topic search and book information.
- Atomic inventory and price updates.
- Input validation and JSON error responses.
- SQLite persistence and Docker volume storage.
- 21 passing HTTP integration tests.

The current Compose file starts Catalog only.
Order, Frontend, and complete purchase integration remain pending.
This repository is not yet the complete lab submission.

## Requirements

- Docker Engine with Docker Compose.
- Python 3.12 and the venv module for running tests or local development.
- On Windows: Docker Desktop with WSL 2 integration enabled.

## Run Catalog with Docker

From the repository root:

```bash
docker compose up -d --build catalog
docker compose ps
curl -i http://localhost:5001/health
```

Expected response:

```json
{"service":"catalog","status":"ok"}
```

View component logs:

```bash
docker compose logs catalog
```

Stop containers without deleting stored data:

```bash
docker compose down
```

Catalog data is stored in the named volume catalog_data.
Do not use docker compose down -v unless you intend to delete that data.

## Example Requests

Search by topic:

```bash
curl -i "http://localhost:5001/search/distributed%20systems"
```

Get book details:

```bash
curl -i http://localhost:5001/info/2
```

Add one copy to inventory:

```bash
curl -i -X PATCH http://localhost:5001/update/2 \
  -H "Content-Type: application/json" \
  -d '{"quantity_delta":1}'
```

Update the price:

```bash
curl -i -X PATCH http://localhost:5001/update/2 \
  -H "Content-Type: application/json" \
  -d '{"price":45}'
```

The last two examples modify stored data.

## Run Catalog Locally

Stop the Docker Catalog first to release port 5001.

```bash
docker compose stop catalog
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r catalog/requirements.txt
python catalog/app.py
```

The local database defaults to catalog/catalog.db.
Docker uses /data/catalog.db inside its persistent volume.
These are separate databases.

## Run Integration Tests

Keep Catalog running. In another terminal, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install requests pytest
python -m pytest tests/catalog -v
```

The tests default to http://localhost:5001.
Set CATALOG_URL to test another Catalog instance.

Update tests temporarily change book 2 and restore its original
quantity and price. Run against a dedicated test instance without
other purchases or inventory updates. Do not run tests in parallel.

## Documentation

- [API contract](docs/api-contract.md)
- [Catalog setup and design](docs/catalog-guide.md)
- [Query test output](docs/catalog-query-tests.txt)
- [Update and concurrency test output](docs/catalog-update-tests.txt)

## Remaining Submission Work

- Integrate Order and Frontend with Catalog.
- Complete Docker Compose deployment for all three services.
- Verify full purchase flow, failures, and concurrent purchases.
- Capture actual client and component output, including purchase messages.
- Complete the combined 2–3 page design document in docs/.
- Update this README with full-system run instructions and final status.
