"""
API v1 router
"""

from fastapi import APIRouter
from app.api.api_v1.endpoints import hosts, wol, discovery, debug

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(hosts.router, prefix="/hosts", tags=["hosts"])
api_router.include_router(wol.router, prefix="/wol", tags=["wake-on-lan"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["discovery"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])

