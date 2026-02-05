"""
Routers del Sistema FUEC
"""
from .auth import router as auth_router
from .admin import router as admin_router
from .conductor import router as conductor_router

__all__ = ["auth_router", "admin_router", "conductor_router"]
