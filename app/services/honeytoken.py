import secrets
import string
from sqlalchemy.orm import Session
from app.db_models import Honeytoken
from datetime import datetime, timedelta
from typing import List

class HoneytokenService:
    _cache: List[str] = None
    _cache_expiry = datetime.min
    _cache_map: dict = None # Map token to ID/Details if needed? For now just detecting existence.

    @staticmethod
    def generate_token(type_str: str) -> str:
        # Maps to HoneytokenType enum values
        if type_str == "AWS Access Key":
            # Start with AKIA (standard AWS ID prefix) + 16 alphanum
            return "AKIA" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        elif type_str == "Database Credentials":
            return "postgres://prod_admin:" + secrets.token_hex(4) + "@db-prod.internal:5432/secrets"
        elif type_str == "Canary Webhook":
             # Fake URL
             return f"https://api.internal-ops.com/hooks/{secrets.token_urlsafe(16)}"
        else:
            return "HT-" + secrets.token_hex(12)

    @staticmethod
    def create_honeytoken(db: Session, type_str: str, description: str, created_by: str) -> Honeytoken:
        token = HoneytokenService.generate_token(type_str)
        ht = Honeytoken(
            token=token,
            type=type_str,
            description=description,
            created_by=created_by,
            is_active=True
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)
        HoneytokenService._cache = None # Invalidate
        return ht

    @staticmethod
    def get_all(db: Session):
        return db.query(Honeytoken).all()

    @staticmethod
    def delete_token(db: Session, token_id: int):
        ht = db.query(Honeytoken).filter(Honeytoken.id == token_id).first()
        if ht:
            db.delete(ht)
            db.commit()
            HoneytokenService._cache = None

    @staticmethod
    def get_active_tokens(db: Session) -> List[str]:
        # Simple TTL caching
        now = datetime.utcnow()
        if HoneytokenService._cache is not None and now < HoneytokenService._cache_expiry:
            return HoneytokenService._cache
        
        results = db.query(Honeytoken.token).filter(Honeytoken.is_active == True).all()
        token_list = [r[0] for r in results]
        HoneytokenService._cache = token_list
        HoneytokenService._cache_expiry = now + timedelta(minutes=1)
        return token_list

    @staticmethod
    def check_content(db: Session, content: str) -> str:
        """
        Checks if content contains any active honeytoken.
        Returns the token found, or None.
        """
        tokens = HoneytokenService.get_active_tokens(db)
        # Check matching
        # Optimization: use Aho-Corasick if many tokens. For now, iteration.
        for t in tokens:
            if t in content:
                # Trigger detected!
                HoneytokenService.increment_trigger_count(db, t)
                return t
        return None

    @staticmethod
    def increment_trigger_count(db: Session, token: str):
        # We start a new transaction or reuse? 
        # CAUTION: If called from Ingest which might be async or inside another txn.
        # Ideally, fire and forget or quick update.
        try:
            ht = db.query(Honeytoken).filter(Honeytoken.token == token).first()
            if ht:
                ht.trigger_count += 1
                db.commit()
        except Exception:
            db.rollback()
