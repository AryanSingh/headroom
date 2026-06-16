import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    from headroom_ee.audit.api import router as audit_router
    router.include_router(audit_router)
    logger.info("Enterprise Audit API routes loaded successfully.")
except ImportError:
    logger.debug("Enterprise audit module (headroom_ee) not found. Audit routes disabled.")
