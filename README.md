# Asynchronous Payment Processing Service

This is a microservice for asynchronous payment processing built with FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, and RabbitMQ (via FastStream).

## Architecture & Features
- **API (FastAPI)**: Accepts payment creation and status check requests. Secured via an API Key in the `X-API-Key` header.
- **Database (PostgreSQL + SQLAlchemy)**: Uses Async SQLAlchemy for maximum performance. Includes tables for `payments` and `outbox_events`.
- **Outbox Pattern**: Guarantees event delivery. Payments are saved and an outbox event is created in the same transaction. A separate `outbox_relay` worker reads the outbox and publishes to RabbitMQ.
- **Idempotency**: Prevents duplicate payments. The `Idempotency-Key` header ensures that repeated requests with the same key do not create duplicate records.
- **Message Broker (RabbitMQ + FastStream)**: Asynchronously processes payments.
- **Retries & DLQ**: Uses `tenacity` for exponential backoff on webhook failures (up to 3 attempts). If completely unprocessable, the message is routed to a Dead Letter Exchange (`payments.dlx`).

## Tech Stack
- FastAPI, Pydantic v2
- SQLAlchemy 2.0, asyncpg, Alembic
- FastStream, RabbitMQ
- Docker, Docker Compose

## Setup and Running

1. **Environment Variables**: First, prepare your environment configuration:
   ```bash
   cp .env.example .env
   ```
   (Feel free to modify the values in `.env` if needed, particularly `API_KEY`)

2. **Docker Setup**: You can spin up the entire application using Docker Compose:

```bash
docker-compose up --build
```

This will start:
- `db`: PostgreSQL database
- `rabbitmq`: Message broker (with Management UI on port 15672)
- `api`: FastAPI application on port 8000
- `consumer`: FastStream RabbitMQ worker to process payments
- `outbox_relay`: Background job reading from `outbox_events` and publishing to RabbitMQ

*Note: Alembic migrations run automatically on API startup.*

## Usage Examples

### 1. Create a Payment

```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
     -H "X-API-Key: my-secret-api-key" \
     -H "Idempotency-Key: unique-key-12345" \
     -H "Content-Type: application/json" \
     -d '{
           "amount": 100.50,
           "currency": "USD",
           "description": "Test Payment",
           "metadata": {"user_id": "999"},
           "webhook_url": "https://httpbin.org/post"
         }'
```

**Response (202 Accepted):**
```json
{
  "id": "e98df8b9-4674-4b53-b09e-7fb7db201127",
  "status": "pending",
  "created_at": "2026-05-30T10:00:00.000Z"
}
```

### 2. Get Payment Information

```bash
curl -X GET "http://localhost:8000/api/v1/payments/e98df8b9-4674-4b53-b09e-7fb7db201127" \
     -H "X-API-Key: my-secret-api-key"
```

**Response:**
```json
{
  "id": "e98df8b9-4674-4b53-b09e-7fb7db201127",
  "status": "succeeded",
  "created_at": "2026-05-30T10:00:00.000Z",
  "amount": 100.5,
  "currency": "USD",
  "description": "Test Payment",
  "metadata": {"user_id": "999"},
  "webhook_url": "https://httpbin.org/post",
  "updated_at": "2026-05-30T10:00:03.000Z",
  "idempotency_key": "unique-key-12345"
}
```

## Testing Webhooks
The examples above use `https://httpbin.org/post` for the webhook. You can check the responses there or start your own webhook listener (e.g., using `ngrok`).
If the webhook endpoint is unreachable or returns a 5xx error, the worker will automatically retry up to 3 times with exponential backoff before sending the event to the Dead Letter Exchange (`payments.dlx`).
