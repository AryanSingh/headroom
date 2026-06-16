from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Policy(Base):
    """Configuration policy for an organization or workspace.

    This dictates budgets, rate limits, and allowed models.
    """

    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=True, index=True)

    # Versioning
    version = Column(Integer, nullable=False, default=1)

    # Budgeting
    budget_limit_usd = Column(Float, nullable=True)
    budget_period = Column(String, nullable=True)  # "daily", "monthly", "hourly"

    # Rate Limiting
    rpm_limit = Column(Integer, nullable=True)
    tpm_limit = Column(Integer, nullable=True)

    # Allowed Models (comma separated)
    allowed_models = Column(Text, nullable=True)

    # Other restrictions
    require_compression = Column(Boolean, nullable=False, default=False)
