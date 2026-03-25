from elasticsearch import Elasticsearch, AsyncElasticsearch
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Synchronous Client (for worker.py)
es_client = Elasticsearch(settings.ELASTICSEARCH_URL)

# Asynchronous Client (for FastAPI)
async_es_client = AsyncElasticsearch(settings.ELASTICSEARCH_URL)

LOGS_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "source": {"type": "keyword"},
            "content": {"type": "text"},
            "predicted_label": {"type": "integer"},
            "final_label": {"type": "integer"},
            "risk_score": {"type": "float"},
            "verdict": {"type": "keyword"},
            "explanation": {"type": "text"},
            "threat_intel": {"type": "object"} # Store JSON as object
        }
    }
}

ALERTS_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "log_timestamp": {"type": "date"},
            "rule_name": {"type": "keyword"},
            "status": {"type": "keyword"},
            "mitre_tactic": {"type": "keyword"},
            "mitre_technique": {"type": "keyword"}
        }
    }
}

def init_indexes():
    """Initializes Elasticsearch indexes if they don't exist."""
    if not settings.ES_ENABLED:
        return

    try:
        if not es_client.indices.exists(index=settings.ES_INDEX_LOGS):
            es_client.indices.create(index=settings.ES_INDEX_LOGS, body=LOGS_MAPPING)
            logger.info(f"✅ Created ES index: {settings.ES_INDEX_LOGS}")
        
        if not es_client.indices.exists(index=settings.ES_INDEX_ALERTS):
            es_client.indices.create(index=settings.ES_INDEX_ALERTS, body=ALERTS_MAPPING)
            logger.info(f"✅ Created ES index: {settings.ES_INDEX_ALERTS}")
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize Elasticsearch indexes: {e}")

async def async_init_indexes():
    """Initializes Elasticsearch indexes (Async version)."""
    if not settings.ES_ENABLED:
        return

    try:
        if not await async_es_client.indices.exists(index=settings.ES_INDEX_LOGS):
            await async_es_client.indices.create(index=settings.ES_INDEX_LOGS, body=LOGS_MAPPING)
            logger.info(f"✅ Created ES index (Async): {settings.ES_INDEX_LOGS}")
            
        if not await async_es_client.indices.exists(index=settings.ES_INDEX_ALERTS):
            await async_es_client.indices.create(index=settings.ES_INDEX_ALERTS, body=ALERTS_MAPPING)
            logger.info(f"✅ Created ES index (Async): {settings.ES_INDEX_ALERTS}")
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize Elasticsearch indexes (Async): {e}")
