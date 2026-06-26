"""FastAPI application entrypoint for the crypto market screener."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import autotrain
from .auth import get_current_user
from .config import settings
from .db import init_db
from .exchanges import manager
from .routers import admin, auth_router, chat, market, metrics, ml

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task: asyncio.Task | None = None
    if settings.autotrain_enabled:
        task = asyncio.create_task(autotrain.run_loop())
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await manager.close()


app = FastAPI(
    title="Crypto Market Screener",
    description=(
        "Multi-exchange screener: order-book density detection, cross-exchange "
        "price comparison, and a self-learning movement classifier."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(get_current_user)]
app.include_router(auth_router.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(market.router, dependencies=_auth)
app.include_router(ml.router, dependencies=_auth)
app.include_router(metrics.router, dependencies=_auth)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
