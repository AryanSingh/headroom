import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    from headroom_ee.policy.api import router as policy_router
    router.include_router(policy_router)
    logger.info("Enterprise Policy API routes loaded successfully.")
except ImportError:
    logger.debug("Enterprise policy module (headroom_ee) not found. Policy routes disabled.")
