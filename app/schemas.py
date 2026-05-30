from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional, Any, Literal
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from enum import Enum
from app.models import PaymentStatus

class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: Literal["RUB", "USD", "EUR"]
    description: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")
    webhook_url: HttpUrl

    model_config = ConfigDict(populate_by_name=True)

class PaymentResponse(BaseModel):
    payment_id: UUID = Field(validation_alias="id")
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class PaymentDetailResponse(PaymentResponse):
    amount: Decimal
    currency: Literal["RUB", "USD", "EUR"]
    description: Optional[str]
    metadata_: Optional[dict[str, Any]] = Field(alias="metadata")
    webhook_url: str
    updated_at: datetime
    idempotency_key: str
