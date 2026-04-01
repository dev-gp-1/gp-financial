import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import integrations

# Configure structured logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gp.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up GP Financial backend...")
    # Cloud SQL asyncpg connection pool initialization would go here in step 2
    yield
    logger.info("Shutting down GP Financial backend...")
    # Close connection pool here

app = FastAPI(
    title="GP Financial API",
    description="Ghost Protocol Financial Platform - Multi-client AR/AP Evaluation Engine",
    version="1.0.0",
    lifespan=lifespan,
)

import os
# CORS configuration to allow local dashboard and any deployment origin
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://ghostprotocol.ai")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        FRONTEND_URL,
        "https://gp-financial-dashboard-*.run.app"
    ],
    allow_origin_regex=r"^https://gp-financial-dashboard.*\.run\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
async def health_check():
    """Cloud Run readiness probe endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

# Include routers
app.include_router(integrations.router, prefix="/api/integrations")

if __name__ == "__main__":
    import uvicorn
    # Typically run via Docker CMD, but this allows direct python execution
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
