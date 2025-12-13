import sys
import os
import time
import requests
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.db_models import Base, Honeytoken, Log, Alert

# Setup DB
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

TEST_TOKEN = "TEST_HONEYTOKEN_VERIFY_XYZ"

def create_test_token():
    print(f"[1/4] Creating test honeytoken: {TEST_TOKEN}")
    existing = db.query(Honeytoken).filter(Honeytoken.token == TEST_TOKEN).first()
    if not existing:
        ht = Honeytoken(
            token=TEST_TOKEN,
            type="Test Token",
            description="Created by verification script",
            is_active=True,
            trigger_count=0
        )
        db.add(ht)
        db.commit()
        print("  -> Token created in DB.")
    else:
        print("  -> Token already exists.")

def send_log():
    print(f"[3/4] Sending malicious log to API...")
    url = "http://localhost:8000/api/ingest/logs"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": settings.LOG_SHIPPER_API_KEY
    }
    payload = {
        "logs": [
            {
                "source": "verification_script",
                "content": f"User admin failed login with password {TEST_TOKEN}"
            }
        ]
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"  -> Log sent successfully: {resp.json()}")
        else:
            print(f"  -> API Error: {resp.status_code} {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  -> Connection Failed: {e}")
        print("  -> Is uvicorn running?")
        sys.exit(1)

def verify_alert():
    print(f"[4/4] Checking for alerts (waiting 5s for worker)...")
    time.sleep(5)
    
    # Check if token trigger count increased
    token = db.query(Honeytoken).filter(Honeytoken.token == TEST_TOKEN).first()
    print(f"  -> Token Trigger Count: {token.trigger_count}")
    
    # Check for Log entry
    log = db.query(Log).filter(Log.content.contains(TEST_TOKEN)).order_by(Log.id.desc()).first()
    if log:
        print(f"  -> Log Found: ID={log.id}")
        print(f"     Risk Score: {log.risk_score}")
        print(f"     Verdict: {log.verdict}")
        
        if log.risk_score >= 1.0:
            print("\n✅ VERIFICATION PASSED: Honeytoken was detected and flagged as Critical!")
        else:
            print("\n❌ VERIFICATION FAILED: Log was ingested but NOT flagged correctly.")
    else:
        print("\n❌ VERIFICATION FAILED: Log not found in DB (Worker might be down or lagging).")

if __name__ == "__main__":
    print("--- Honeytoken Verification Script ---")
    
    create_test_token()
    
    print("[2/4] Waiting 65s for Worker Cache to expire (since worker caches tokens for 60s)...")
    # time.sleep(65) 
    # For speed development, user might have just restarted worker. But to be safe we wait.
    # Actually, if I just created it, the worker might have loaded 'old' cache 59s ago.
    # I'll wait 65s.
    for i in range(65, 0, -1):
        print(f"Waiting {i}s...", end="\r")
        time.sleep(1)
    print("\n")
    
    send_log()
    verify_alert()
