"""
KL HRMS API — FastAPI application entry point.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.role.route import router as role_router

app = FastAPI(
    title="KL HRMS API",
    version="1.0.0",
    description="KL HRMS — multi-tenant SaaS HRMS backend",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(role_router)


@app.get("/", tags=["root"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "KL HRMS API", "docs": "/docs"}
