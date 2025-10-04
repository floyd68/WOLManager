"""
WOLManager - A Modern Network Host Discovery and WOL Broadcast Service
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.redis_client import redis_client
from app.services.discovery_service import DiscoveryService
from app.services.wol_service import WOLService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="WOLManager",
    description="A Modern Network Host Discovery and WOL Broadcast Service",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Initialize services
discovery_service = DiscoveryService()
wol_service = WOLService()


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting WOLManager application")
    
    # Test Redis connection
    try:
        await redis_client.connect()
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        # Don't raise - allow app to start without Redis for now
        logger.warning("Continuing without Redis - some features may not work")
    
    # Start background discovery service
    try:
        await discovery_service.start()
        logger.info("Discovery service started")
    except Exception as e:
        logger.error("Failed to start discovery service", error=str(e))
        logger.warning("Continuing without discovery service")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down WOLManager application")
    await discovery_service.stop()
    await redis_client.close()
    logger.info("Application shutdown complete")


@app.get("/")
async def root(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if redis_client.redis:
            await redis_client.ping()
            return {"status": "healthy", "redis": "connected"}
        else:
            return {"status": "healthy", "redis": "not_configured"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        access_log=False
    )
