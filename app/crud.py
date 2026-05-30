from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.models import Payment, OutboxEvent, PaymentStatus, OutboxStatus
from app.schemas import PaymentCreate
import json

async def get_payment_by_idempotency_key(db: AsyncSession, idempotency_key: str) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
    return result.scalar_one_or_none()

async def get_payment(db: AsyncSession, payment_id: str) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()

async def create_payment_with_outbox(db: AsyncSession, payment_in: PaymentCreate, idempotency_key: str) -> Payment:
    # Check idempotency first
    existing = await get_payment_by_idempotency_key(db, idempotency_key)
    if existing:
        return existing

    # Create Payment
    payment = Payment(
        amount=payment_in.amount,
        currency=payment_in.currency,
        description=payment_in.description,
        metadata_=payment_in.metadata_,
        webhook_url=str(payment_in.webhook_url),
        status=PaymentStatus.pending,
        idempotency_key=idempotency_key
    )
    db.add(payment)
    await db.flush() # To get the generated payment.id
    
    # Create Outbox event
    payload = {
        "payment_id": str(payment.id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "webhook_url": payment.webhook_url,
    }
    
    outbox_event = OutboxEvent(
        event_type="payments.new",
        payload=payload,
        status=OutboxStatus.pending
    )
    db.add(outbox_event)
    
    try:
        await db.commit()
        await db.refresh(payment)
        return payment
    except IntegrityError:
        await db.rollback()
        # In case of race condition
        existing = await get_payment_by_idempotency_key(db, idempotency_key)
        if existing:
            return existing
        raise

async def update_payment_status(db: AsyncSession, payment_id: str, status: PaymentStatus) -> Payment | None:
    payment = await get_payment(db, payment_id)
    if payment:
        payment.status = status
        await db.commit()
        await db.refresh(payment)
    return payment
