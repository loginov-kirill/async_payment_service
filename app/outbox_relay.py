import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from faststream.rabbit import RabbitBroker
from pydantic import BaseModel
import sys

from app.database import AsyncSessionLocal
from app.models import OutboxEvent, OutboxStatus
from app.config import settings

class PaymentMessage(BaseModel):
    payment_id: str
    amount: str
    currency: str
    webhook_url: str

async def relay_outbox_events():
    broker = RabbitBroker(settings.RABBITMQ_URL)
    await broker.connect()
    
    try:
        while True:
            async with AsyncSessionLocal() as db:
                # Find pending events
                result = await db.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.status == OutboxStatus.pending)
                    .order_by(OutboxEvent.created_at.asc())
                    .limit(50)
                )
                events = result.scalars().all()
                
                for event in events:
                    # Publish to RabbitMQ
                    msg = PaymentMessage(**event.payload)
                    try:
                        await broker.publish(
                            msg,
                            exchange="payments",
                            routing_key=event.event_type
                        )
                        # Mark as processed
                        event.status = OutboxStatus.processed
                        await db.commit()
                        print(f"Relayed outbox event {event.id} to {event.event_type}")
                    except Exception as e:
                        print(f"Failed to publish event {event.id}: {e}")
                        await db.rollback()
                        
            # Sleep before next poll
            await asyncio.sleep(2)
            
    finally:
        await broker.close()

if __name__ == "__main__":
    try:
        asyncio.run(relay_outbox_events())
    except KeyboardInterrupt:
        pass
