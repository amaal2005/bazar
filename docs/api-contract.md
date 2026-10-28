# Bazar.com — API Contract v1.1

Distributed and Operating Systems — Fall 2026 — Lab 1

This document is the shared agreement between the two developers. Agree on and commit any contract change before using it. Initial quantities and prices are team choices, not assignment requirements. This document specifies intended behavior; implementation and testing are separate tasks.

## 1. Technology and architecture

- Python and Flask for all three services; SQLite for persistence.
- Three Linux containers managed by Docker Compose.
- All inter-service communication uses HTTP REST; API responses are JSON.
- A Python command-line client runs on the host. No GUI is required.
- Each service owns its database. No service directly accesses another service's database.

## 2. Addresses and configuration

| Service | Compose name | Port | Internal URL |
|---|---|---|---|
| Frontend | frontend | 5000 | http://frontend:5000 |
| Catalog | catalog | 5001 | http://catalog:5001 |
| Order | order | 5002 | http://order:5002 |

The client uses http://localhost:5000. Ports 5001 and 5002 may be published for direct testing. Services listen on 0.0.0.0. Inside containers, use service names rather than localhost to contact another service.

Frontend reads CATALOG_URL and ORDER_URL from environment variables; Order reads CATALOG_URL. Compose supplies the URLs above. Use a 5-second timeout for each internal HTTP call and a 15-second client timeout for purchases. Do not automatically retry purchases or inventory updates.

## 3. Initial catalog

| id | title | topic | quantity | price |
|---|---|---|---|---|
| 1 | How to get a good grade in DOS in 40 minutes a day. | distributed systems | 10 | 40.00 |
| 2 | RPCs for Noobs. | distributed systems | 10 | 50.00 |
| 3 | Xen and the Art of Surviving Undergraduate School. | undergraduate school | 10 | 60.00 |
| 4 | Cooking for the Impatient Undergrad. | undergraduate school | 10 | 30.00 |

Seed the books only when creating the database. Restarting must not reset quantities or prices. These titles, including their final periods, are canonical across data, mocks, tests, and logs; they follow the original list despite punctuation differences in the appendix.

Prices are JSON numbers in one agreed price unit. Store them internally as integer minor units to avoid floating-point arithmetic errors. Payment, taxes, and shipping are outside scope.

## 4. Common rules

- Item ids are positive integers. Invalid ids return 400; valid but nonexistent ids return 404.
- Boolean values are not valid numeric inputs.
- Search results are sorted by ascending id.
- Trim topic whitespace and compare topics case-insensitively. An unknown topic returns [] with 200.
- URL-encode spaces, for example distributed%20systems.
- Purchase POST requests have no body. PATCH requires Content-Type: application/json.
- Prices must be finite, nonnegative numbers with at most two decimal places.
- Use quantity and price, not alternative field names such as stock or cost.
- Route, method, and JSON parsing errors must return JSON rather than default HTML error pages.

## 5. Search

GET /search/<topic>

Available on Frontend and Catalog. Frontend forwards to Catalog and preserves the response structure. This implements query-by-subject; no additional /query endpoint is needed.

200 response:

```json
[
  {"id": 1, "title": "How to get a good grade in DOS in 40 minutes a day."},
  {"id": 2, "title": "RPCs for Noobs."}
]
```

## 6. Info

GET /info/<id>

Available on Frontend and Catalog. Implements query-by-item. The id and topic fields supplement the appendix's required title, quantity, and price fields.

200 response:

```json
{
  "id": 2,
  "title": "RPCs for Noobs.",
  "topic": "distributed systems",
  "quantity": 10,
  "price": 50.00
}
```

## 7. Update — Catalog only

PATCH /update/<id>

Accept either or both fields, applying all changes in one transaction:

```json
{"quantity_delta": 5}
```

```json
{"price": 45.00}
```

```json
{"quantity_delta": -1, "price": 45.00}
```

quantity_delta is a nonzero integer: positive adds stock; negative removes stock. Reject empty objects, unknown fields, or invalid values with 400. An inappropriate content type returns 415.

If the resulting stock would be negative, return 409 without changing any field. A valid but nonexistent id returns 404 BOOK_NOT_FOUND, including when quantity_delta is -1.

Success returns 200 with the complete updated book using the Info schema. The price returned after a decrement is read within that decrement transaction and is used by Order as the purchase price.

Concurrency requirement: checking and decrementing inventory must be atomic. An unprotected SELECT followed by a separate UPDATE is insufficient. A conditional UPDATE and affected-row check are acceptable when existence checks and the result read remain within the protected transaction.

Agreed sequence: BEGIN IMMEDIATE, check book existence and stock, UPDATE, SELECT the complete updated book including price, then COMMIT. Retain the selected values and return them only after a successful commit. Do not read price in a new transaction or connection. Roll back on failure.

Periodic restocking uses this endpoint. An automatic restocking timer is not required.

## 8. Purchase — Frontend and Order

POST /purchase/<id>

Each request purchases one copy. Frontend forwards to Order.

Order processing:

1. Call Catalog GET /info/<id> to check book existence and stock.
2. If quantity is zero, return 409 without recording a successful order.
3. Call Catalog PATCH /update/<id> with {"quantity_delta": -1}.
4. Treat the atomic decrement result as authoritative, regardless of the earlier stock check.
5. Persist the order in Order's SQLite database, then return 201.
6. Never record failed purchases as successful orders.

201 response:

```json
{
  "message": "bought book RPCs for Noobs.",
  "order": {
    "order_id": 1,
    "item_id": 2,
    "title": "RPCs for Noobs.",
    "quantity": 1,
    "price": 50.00,
    "created_at": "2026-10-28T12:00:00Z"
  }
}
```

order_id is a positive integer unique within the orders database. created_at is a UTC ISO 8601 timestamp. The example id and timestamp are illustrative. If price changes between Info and Update, record the price returned by Update.

The client prints message on purchase success only. Order must also print bought book followed by a space and the canonical title to stdout, only after successfully committing the order. Returning JSON alone is insufficient.

```text
bought book RPCs for Noobs.
```

Services also log incoming requests and outcomes. Capture actual client and service output for submission.

## 9. Errors

All errors use this structure:

```json
{
  "error": {
    "code": "OUT_OF_STOCK",
    "message": "Book is out of stock."
  }
}
```

| HTTP | code | Meaning |
|---|---|---|
| 400 | INVALID_REQUEST | Invalid id, JSON, or field values |
| 404 | BOOK_NOT_FOUND | Book does not exist |
| 404 | ROUTE_NOT_FOUND | Route does not exist |
| 405 | METHOD_NOT_ALLOWED | Unsupported HTTP method |
| 409 | OUT_OF_STOCK | Insufficient stock for the requested decrement |
| 415 | UNSUPPORTED_MEDIA_TYPE | PATCH content type is not application/json |
| 500 | INTERNAL_ERROR | Internal error or failure to persist an order |
| 502 | INVALID_UPSTREAM_RESPONSE | Another service returned invalid data or violated the contract |
| 503 | SERVICE_UNAVAILABLE | Required service is unreachable, or database remains busy after lock waiting expires |
| 504 | UPSTREAM_TIMEOUT | A required service exceeded the HTTP timeout |

Preserve valid business errors such as 404 and 409, including status and body. Frontend preserves valid contract responses from Catalog and Order; it must not convert failure into 200. Log diagnostics internally without exposing SQL details or stack traces to clients.

## 10. Health and storage

GET /health on each service returns 200:

```json
{"status": "ok", "service": "catalog"}
```

Use the actual service name: catalog, order, or frontend. This local check does not guarantee that all other services are healthy.

- Catalog: /data/catalog.db in its own persistent volume.
- Order: /data/orders.db in a separate persistent volume.
- Frontend has no database.
- Use a separate SQLite connection per request and short transactions.
- Use sqlite3.connect(path, timeout=5), enable PRAGMA journal_mode=WAL during database initialization, and use BEGIN IMMEDIATE for Catalog update transactions.
- These settings reduce lock contention but do not eliminate all busy errors. If lock waiting expires, roll back and return 503.
- Container restarts preserve data. docker compose down -v removes volumes; use it only for an intentional test reset.

## 11. Responsibilities and independent development

| Developer A | Developer B |
|---|---|
| Catalog, books database, and seed data | Order and orders database |
| Atomic updates and stock protection | Frontend, forwarding, and error propagation |
| Catalog Dockerfile and compose.yaml | Order and Frontend Dockerfiles |
| Catalog tests and post-integration concurrency tests | Order and Frontend tests, plus client script |
| README, run instructions, and Catalog design section | Execution output, Order and Frontend design sections, and limitations |

Developer A tests Catalog directly without waiting for other services. Developer B uses a Catalog mock for Order tests and backend mocks for Frontend tests. Mocks follow the exact endpoints, schemas, and status codes, including successful Info followed by Update returning 409.

Do not access the other service's database. Discuss and commit contract changes before relying on them. Both developers make meaningful incremental commits throughout development rather than one final bulk commit.

## 12. Integration acceptance checks

- Each known topic returns two books in order; an unknown topic returns [].
- Info returns book details; nonexistent books return 404.
- Successful purchase returns 201, decrements stock by one, and records one order.
- Purchase with zero stock returns 409 and records no successful order.
- With initial stock of one and ten concurrent purchases in a healthy, failure-free run: exactly one succeeds, nine return 409, final stock is zero, and one successful order exists.
- PATCH with quantity_delta -1 returns 404 BOOK_NOT_FOUND for a nonexistent book and 409 OUT_OF_STOCK for an existing book with zero stock.
- Titles match the canonical table exactly; PATCH returns the price read within its transaction.
- Restocking and price changes work; invalid inputs do not change stored data.
- Stopping a required backend produces an appropriate JSON error, never a false purchase success.
- Restarting containers preserves catalog and orders.
- Client Search and Info output is clearly formatted; successful purchase output includes bought book followed by the title.
- Order stdout includes the purchase message only after a successful order commit.
- Save actual execution output in docs/output.txt. Save the final 2–3 page design document in docs/, explaining operation, run instructions, tradeoffs, limitations, and extensions.

## 13. Version-one limitations

Atomic inventory updates prevent overselling during normal operation, but Catalog and Order do not share a distributed transaction. If decrement commits and Order crashes before saving the order, inventory may decrease without an order record.

A connection failure after execution may leave the client uncertain whether purchase completed. Repeating POST may create another purchase. This version provides neither exactly-once nor idempotency guarantees. Do not blindly add stock as compensation after a timeout; the actual outcome may be unknown.

Document these cases in the design report. Future improvements could include stable purchase identifiers, idempotent reservation and confirmation operations, and reconciliation. Security hardening, authentication, and TLS are outside the scope of this local version.

## 14. Implementation start

1. Place this file at docs/api-contract.md in the shared GitHub repository.
2. Commit the agreed contract before implementation.
3. Create branches feature/catalog and feature/order-frontend.
4. Each developer implements and tests her assigned components independently.
5. Integrate using Docker Compose and run the acceptance checks above.
