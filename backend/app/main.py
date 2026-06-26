"""FastAPI application entrypoint for the crypto market screener."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .exchanges import manager
from .routers import market, ml


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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

app.include_router(market.router)
app.include_router(ml.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
