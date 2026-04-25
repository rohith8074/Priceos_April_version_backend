from fastapi import FastAPI, Request, Response
import json
import time
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import init_db
from app.api.auth import auth_router
from app.api.engine import engine_router
from app.api.listings import listings_router
from app.api.rules import rules_router
from app.api.inventory import inventory_router
from app.api.market_setup import market_setup_router
from app.api.placeholders import (
    hostaway_router, sync_router, proposals_router, 
    calendar_metrics_router, insights_router, organizations_router, 
    properties_router, reservations_router, benchmark_router, chat_router, events_router
)
from app.api.agent_tools import agent_tools_router
from app.api.guest_agent import guest_agent_router
from app.api.admin import admin_router
from app.api.groups import groups_router
from app.api.sync_ops import sync_ops_router
from app.api.user_settings import user_settings_router, markets_router
from app.api.proposals_ops import proposals_ops_router, revenue_v1_router
from app.api.engagement_ops import engagement_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Beanie on startup
    await init_db()
    yield
    # Clean up on shutdown if necessary

app = FastAPI(title="PriceOS API", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_agent_interactions(request: Request, call_next):
    path = request.url.path
    # We focus on logging tools and agent-facing endpoints
    is_agent_endpoint = any(path.startswith(p) for p in ["/api/agent-tools", "/api/guest-agent", "/api/market-setup", "/api/chat"])
    
    if not is_agent_endpoint:
        return await call_next(request)

    print(f"\n[API CALL] {request.method} {path}")
    if request.query_params:
        print(f"  Query: {request.query_params}")

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # 2. Capture and Log Output (Skip for streaming responses)
    if response.media_type == "text/event-stream":
        print(f"[TOOL/API RESPONSE] {path} | Status: {response.status_code} | {duration:.3f}s | STREAMING")
        return response

    response_body = b""
    if hasattr(response, "body_iterator"):
        async for chunk in response.body_iterator:
            response_body += chunk
    elif hasattr(response, "body"):
        response_body = response.body
    
    print(f"[TOOL/API RESPONSE] {path} | Status: {response.status_code} | {duration:.3f}s")
    try:
        print(f"  Output: {response_body.decode()[:2000]}")
    except:
        print("  Output: <binary/stream>")

    # We must return a new response object because the body_iterator has been consumed
    # or the original body is encapsulated.
    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )

app.include_router(auth_router, prefix="/api")
app.include_router(engine_router, prefix="/api")
app.include_router(listings_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(market_setup_router, prefix="/api")

# Placeholders to prevent 404s
app.include_router(hostaway_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(proposals_router, prefix="/api")
app.include_router(calendar_metrics_router, prefix="/api")
app.include_router(insights_router, prefix="/api")
app.include_router(organizations_router, prefix="/api")
app.include_router(properties_router, prefix="/api")
app.include_router(reservations_router, prefix="/api")
app.include_router(benchmark_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(agent_tools_router, prefix="/api")
app.include_router(guest_agent_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(sync_ops_router, prefix="/api")
app.include_router(user_settings_router, prefix="/api")
app.include_router(markets_router, prefix="/api")
app.include_router(proposals_ops_router, prefix="/api")
app.include_router(revenue_v1_router, prefix="/api")
app.include_router(engagement_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "priceos-api", "version": "1.0.0"}
