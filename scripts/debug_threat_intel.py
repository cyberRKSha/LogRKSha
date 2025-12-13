
import os
import sys
import json
import requests
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.config import settings

def debug_threat_intel():
    print("--- Debugging Threat Intelligence ---")
    
    # 1. Check API Key
    api_key = settings.ABUSEIPDB_API_KEY
    if not api_key:
        print("❌ ABUSEIPDB_API_KEY is NOT set in settings!")
        print("   Please add it to your .env file: ABUSEIPDB_API_KEY=...")
    else:
        print(f"✅ ABUSEIPDB_API_KEY is set (Length: {len(api_key)})")
        
        # 1.5 Test API connection
        print("   Testing API connection manually...")
        try:
            headers = {'Key': api_key, 'Accept': 'application/json'}
            params = {'ipAddress': '1.1.1.1', 'maxAgeInDays': '90'}
            r = requests.get('https://api.abuseipdb.com/api/v2/check', headers=headers, params=params, timeout=5)
            if r.status_code == 200:
                print("   ✅ AbuseIPDB API connection successful!")
            elif r.status_code == 401:
                print("   ❌ AbuseIPDB API returned 401 Unauthorized. Key might be invalid.")
            else:
                print(f"   ⚠️ AbuseIPDB API returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"   ❌ Network error connecting to AbuseIPDB: {e}")

    # 2. Check Database for RELEVANT logs
    print("\n--- Checking Database ---")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            # Check for the specific test IP
            print("1. Searching for test IP 118.25.6.39...")
            result = conn.execute(text("SELECT id, content, threat_intel, timestamp FROM logs WHERE content LIKE '%118.25.6.39%' ORDER BY id DESC LIMIT 1")).fetchone()
            
            if result:
                print(f"   Found Log ID: {result.id}")
                if result.threat_intel:
                    print(f"   ✅ Threat Intel Data: {result.threat_intel}")
                else:
                    print(f"   ❌ Threat Intel is NULL (Worker missed it?)")
            else:
                print("   ❌ Test log not found. Did you run the curl command with the IP?")

            # Check if ANY log has threat intel
            print("\n2. Checking if ANY log has Threat Intel...")
            any_ti = conn.execute(text("SELECT count(*) FROM logs WHERE threat_intel IS NOT NULL")).scalar()
            print(f"   Total enriched logs in DB: {any_ti}")


    except Exception as e:
        print(f"❌ Database Error: {e}")

if __name__ == "__main__":
    debug_threat_intel()
