from fastapi import FastAPI, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from uuid import UUID
import secrets

from app.database import get_db
from app.schemas import PaymentCreate, PaymentResponse, PaymentDetailResponse
from app.crud import create_payment_with_outbox, get_payment
from app.config import settings

app = FastAPI(title="Asynchronous Payment Processing Service")

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

@app.post("/api/v1/payments", response_model=PaymentResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_api_key)])
async def create_payment(
    payment_in: PaymentCreate,
    idempotency_key: Annotated[str, Header(..., alias="Idempotency-Key")],
    db: AsyncSession = Depends(get_db)
):
    payment = await create_payment_with_outbox(db, payment_in, idempotency_key)
    return payment

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentDetailResponse, dependencies=[Depends(verify_api_key)])
async def get_payment_info(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    payment = await get_payment(db, str(payment_id))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment
