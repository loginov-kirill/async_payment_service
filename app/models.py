import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"

class OutboxStatus(str, enum.Enum):
    pending = "pending"
    processed = "processed"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    description = Column(String, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    webhook_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(Enum(OutboxStatus), default=OutboxStatus.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
