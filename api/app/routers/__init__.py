"""Routers package"""

from app.routers.addresses import router as addresses_router
from app.routers.emails import router as emails_router

__all__ = ["addresses_router", "emails_router"]
