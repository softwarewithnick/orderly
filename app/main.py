"""Application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.routers import catalog, orders, webhooks

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the database on start, close it on shutdown."""
    db.init_db()
    yield
    db.close_connection()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Orderly",
        version="0.1.0",
        summary="A small order and checkout service",
        lifespan=lifespan,
    )
    app.include_router(catalog.router)
    app.include_router(orders.router)
    app.include_router(webhooks.router)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        """Liveness probe. Deliberately unauthenticated."""
        return {"status": "ok"}

    return app


app = create_app()
