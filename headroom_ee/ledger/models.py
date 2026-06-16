from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass


class SpendEvent(Base):
    __tablename__ = "spend_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Integer, nullable=False, index=True)

    # Tenant Indices
    org_id = Column(String, nullable=True, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    project_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)

    # Payload
    model = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    auth_mode = Column(String, nullable=False)
    request_id = Column(String, nullable=False, index=True)

    # Usage
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    tokens_saved = Column(Integer, nullable=False, default=0)

    # Cost
    est_cost_usd = Column(Float, nullable=True)
    est_cost_saved_usd = Column(Float, nullable=True)
