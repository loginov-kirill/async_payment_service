from faststream import FastStream, Context
from faststream.rabbit import RabbitBroker, RabbitQueue, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage
from faststream.exceptions import AckMessage
import asyncio
import secrets
import socket
import urllib.parse
import ipaddress
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.database import AsyncSessionLocal
from app.crud import update_payment_status, get_payment
from app.models import PaymentStatus

broker = RabbitBroker(settings.RABBITMQ_URL)
app = FastStream(broker)

# Define Exchanges and Queues
exchange = RabbitExchange("payments", auto_delete=False)
dlq_exchange = RabbitExchange("payments.dlx", auto_delete=False)

queue = RabbitQueue(
    "payments.new",
    routing_key="payments.new",
    exchange=exchange,
    arguments={"x-dead-letter-exchange": "payments.dlx"},
    auto_delete=False
)

dlq_queue = RabbitQueue(
    "payments.dlq",
    routing_key="payments.new",
    exchange=dlq_exchange,
    auto_delete=False
)

class PaymentMessage(BaseModel):
    payment_id: str
    amount: str
    currency: str
    webhook_url: str

async def process_payment_emulation():
    # Emulate 2-5 seconds processing
    delay = secrets.SystemRandom().uniform(2, 5)
    await asyncio.sleep(delay)
    
    # Emulate 90% success, 10% error
    if secrets.SystemRandom().random() > 0.9:
        raise ValueError("Payment processing failed (emulated error)")
        
    return True

def is_safe_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.hostname:
            return False
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)
        return not (ip_obj.is_private or ip_obj.is_loopback)
    except Exception:
        return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True
)
async def send_webhook(url: str, payload: dict):
    if not is_safe_url(url):
        raise ValueError(f"Unsafe webhook URL blocked: {url}")

    # Try sending webhook, raising exception on failure
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()

@broker.subscriber(queue)
async def handle_payment(msg: PaymentMessage, raw_message: RabbitMessage = Context("message")):
    async with AsyncSessionLocal() as db:
        # Check idempotency
        payment = await get_payment(db, msg.payment_id)
        if not payment:
            # If payment doesn't exist, we can't do anything. Acknowledge and drop.
            return
            
        if payment.status != PaymentStatus.pending:
            # Already processed, acknowledge and return
            return
            
        try:
            # Emulate processing
            await process_payment_emulation()
            status = PaymentStatus.succeeded
        except Exception as e:
            status = PaymentStatus.failed
            
        # Update Database
        payment = await update_payment_status(db, msg.payment_id, status)
        if not payment:
            # If payment doesn't exist, we can't do anything. Acknowledge and drop.
            return
            
        webhook_payload = {
            "payment_id": msg.payment_id,
            "status": status.value,
        }
        
        try:
            # This will retry up to 3 times with exponential backoff
            await send_webhook(msg.webhook_url, webhook_payload)
        except Exception as e:
            print(f"Webhook failed 3 times for {msg.payment_id}. Moving to DLQ.")
            # Publish to DLQ
            await broker.publish(
                msg,
                exchange=dlq_exchange,
                routing_key="payments.new"
            )
            # Acknowledge the original message so it doesn't get re-processed
            raise AckMessage()
