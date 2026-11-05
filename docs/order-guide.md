# Bazar.com – Order Service Guide

## 1. Overview

The Order Service is responsible for handling book purchase requests.
It communicates with the Catalog Service to check book information
and update the available stock. It also stores successful orders in
its own SQLite database.

The service is built using Python and Flask and runs on port 5002.

## 2. Architecture

The Order Service is one of the three independent microservices
in the Bazar.com system.

Its main responsibilities are:

- Receive purchase requests from the Frontend Service.
- Request book information from the Catalog Service.
- Check whether the book is available.
- Request a stock decrease from the Catalog Service.
- Save the successful purchase in the orders database.
- Return the purchase result to the caller.

The service communicates with the Catalog Service using HTTP
requests and JSON responses.

## 3. Database Design

The Order Service uses SQLite and maintains its own database
named `orders.db`.

The database contains an `orders` table with the following columns:

| Column | Description |
|---|---|
| order_id | Unique order identifier |
| item_id | ID of the purchased book |
| title | Book title |
| quantity | Number of purchased copies (1) |
| price_cents | Book price stored in cents |
| created_at | Order creation time in UTC |

The database uses WAL mode and a connection timeout of 5 seconds.

Existing orders are kept when the service starts again.

## 4. Purchase Process

When a purchase request is received:

1. The service validates the book ID.
2. It requests the book information from the Catalog Service.
3. It checks whether the book exists and has available stock.
4. It sends a request to decrease the stock by one.
5. It uses the updated book information returned by the Catalog Service.
6. It saves the successful order in the local database.
7. It returns HTTP 201 with the order details.

The order is saved only after the stock update succeeds.

## 5. API Endpoints

### GET /health

Checks whether the Order Service is running.

Successful response:

```json
{
  "status": "ok",
  "service": "order"
}
```

### POST /purchase/<item_id>

Purchases one copy of the requested book.

Example:

`POST /purchase/2`

A successful request returns HTTP 201 and includes the order
identifier, book information, price, quantity, and creation time.

## 6. Error Handling

The service handles different failure cases, including:

- Invalid book IDs.
- Books that do not exist.
- Books with no available stock.
- Catalog Service connection failures.
- Upstream request timeouts.
- Invalid responses from the Catalog Service.
- Local database errors.

The service uses appropriate HTTP status codes and JSON error
responses.

It does not automatically retry purchase or stock-update requests.

## 7. Docker

The Order Service has its own Dockerfile.

It uses Python 3.12 slim as its base image and exposes port 5002.

The database path inside the container is:

`/data/orders.db`

A persistent Docker volume should be configured when the service
is added to the complete Docker Compose setup.

## 8. Improvements and Limitations

### Improvements

- Separate database ownership for each microservice.
- Input validation before processing purchases.
- HTTP timeouts when communicating with Catalog.
- Error handling for unavailable services.
- Stock update is confirmed by the Catalog Service before saving
  the order.
- SQLite WAL mode and database connection timeout.

### Limitations

The purchase operation involves two separate services and two
separate databases. If the Catalog Service successfully decreases
the stock but the Order Service stops before saving the order,
the stock may be reduced without a corresponding saved order.

The current design does not implement a distributed transaction
or an idempotency mechanism for duplicate purchase requests.

## 9. Running the Service Locally

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Run the service:

```bash
python app.py
```

The service listens on port 5002.

The Catalog Service URL can be configured using the
`CATALOG_URL` environment variable.

## 10. Current Testing Status

The Order Service was tested using a mock Catalog Service for
independent development.

The tests covered successful purchases, out-of-stock responses,
invalid book IDs, and selected upstream failure cases.

The Docker image was built successfully, and the container health
endpoint returned HTTP 200.

Full integration testing with the Catalog and Frontend Services
will be performed after all three services are connected.
