import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    from headroom_ee.ledger.api import router as spend_router
    router.include_router(spend_router)
    logger.info("Spend ledger API routes loaded successfully.")
except ImportError:
    logger.debug("Enterprise spend ledger module (headroom_ee) not found. Spend routes disabled.")
