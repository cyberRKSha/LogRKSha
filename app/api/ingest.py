# app/api/ingest.py
from fastapi import APIRouter, Header, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
import pika
import json
import logging
import time
from app.config import settings
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.services.honeytoken import HoneytokenService

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])
logger = logging.getLogger(__name__)

# Pydantic model for receiving logs
class LogEntry(BaseModel):
    source: str
    content: str

class LogBatch(BaseModel):
    logs: List[LogEntry]

# --- Persistent Connection Logic ---
class RabbitMQProducer:
    def __init__(self):
        self.connection = None
        self.channel = None

    def connect(self):
        try:
            # Try IPv4 explicitly first (fixes ::1 errors)
            # Or reliance on localhost resolving correctly
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=settings.RABBITMQ_HOST)
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='log_queue', durable=True)
            logger.info("✅ Ingest API connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.connection = None
            self.channel = None

    def publish(self, message: dict):
        if not self.channel or self.connection.is_closed:
            logger.warning("RabbitMQ connection lost. Reconnecting...")
            self.connect()
        
        if not self.channel:
            raise Exception("RabbitMQ unavailable")

        try:
            self.channel.basic_publish(
                exchange='',
                routing_key='log_queue',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
        except (pika.exceptions.ConnectionClosed, pika.exceptions.ChannelClosed) as e:
            logger.warning(f"Publish failed ({e}). Reconnecting and retrying...")
            self.connect()
            if self.channel:
                self.channel.basic_publish(
                    exchange='',
                    routing_key='log_queue',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
            else:
                raise

# Global Producer Instance
producer = RabbitMQProducer()

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Simple API Key validation."""
    if not settings.LOG_SHIPPER_API_KEY:
        return True
    
    if x_api_key != settings.LOG_SHIPPER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return True

@router.post("/logs", status_code=status.HTTP_200_OK)
async def ingest_logs(batch: LogBatch, authorized: bool = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    Receives a batch of logs from a remote shipper and pushes them to RabbitMQ.
    """
    if not batch.logs:
        return {"message": "No logs received"}

    try:
        count = 0
        for log in batch.logs:
            # Check for Honeytokens
            ht_match = HoneytokenService.check_content(db, log.content)
            
            message = {
                "source": log.source,
                "content": log.content,
                "honeytoken": ht_match
            }
            producer.publish(message)
            count += 1
        
        # Log only periodically or for large batches to avoid spam
        # logger.info(f"Ingested {count} logs from shipper.") 
        return {"message": f"Successfully queued {count} logs"}

    except Exception as e:
        logger.error(f"Failed to ingest logs: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during ingestion")
