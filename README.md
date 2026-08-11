# Orderly

A small order + checkout service built with FastAPI. It exists to be *reviewed*.

Orderly models the part of a commerce backend where the interesting bugs live: an
HTTP layer that takes an order, a pricing service that has to be exact about money,
an inventory service that has to be correct under concurrency, and a payment gateway
that talks to the outside world and calls back in via webhooks.

```
POST /orders  ->  orders router  ->  inventory.reserve()
                                 ->  pricing.quote()
                                 ->  payments.authorize()  ->  gateway
                                 <-  POST /webhooks/payments
                                 ->  notifications.send()
```

## Why this repo exists

Every service in here is small enough to read in one sitting and realistic enough
that a code review has something to say about it. That makes it a good target for
[CodeRabbit](https://www.coderabbit.ai/), which reviews pull requests automatically
and is free for public repositories.

See [`docs/DEMO.md`](docs/DEMO.md) for the guided walkthrough.

## Running it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

The API is then at http://127.0.0.1:8000, with interactive docs at `/docs`.

Every request except `/healthz` and `/webhooks/*` needs an API key:

```bash
export ORDERLY_API_KEY=local-dev-key
curl -H "X-API-Key: local-dev-key" http://127.0.0.1:8000/orders
```

## Tests

```bash
pytest
```

## Layout

| Path | What it holds |
| --- | --- |
| `app/routers/` | HTTP surface: request parsing, status codes, nothing else |
| `app/services/` | Business rules: pricing, inventory, payments, notifications |
| `app/db.py` | SQLite access. Every query is parameterized |
| `app/security.py` | API key auth and webhook signature verification |
| `app/models.py` | Pydantic request/response schemas |

## Promo codes

A percentage-off code can be applied at checkout:

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "X-API-Key: $ORDERLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-1",
       "items": [{"sku": "SKU-LAMP", "quantity": 2}],
       "promo_code": "LAUNCH10"}'
```

The storefront can preview a code before checkout with
`GET /promotions/validate?code=LAUNCH10`.

## Money

All money is stored and computed as **integer cents**. There is no float arithmetic
anywhere in the pricing path, and there should never be — see
`app/services/pricing.py` for the rounding rules.

## License

MIT
