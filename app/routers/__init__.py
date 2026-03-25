# Routers Package
from app.routers.auth import router as auth_router
from app.routers.customers import router as customers_router
from app.routers.merchants import router as merchants_router
from app.routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "customers_router",
    "merchants_router",
    "admin_router"
]
