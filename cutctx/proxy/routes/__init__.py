"""Proxy route modules — admin, enterprise, and management endpoints."""

from .admin import create_admin_router

__all__ = ["create_admin_router"]
