# app/audit.py
"""
Audit Logging Module for security-sensitive actions.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from app.config import settings

logger = logging.getLogger(__name__)

class AuditLogger:
    """Centralized audit logging for security events."""
    
    # Action types
    ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
    ACTION_LOGIN_FAILED = "LOGIN_FAILED"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_2FA_ENABLED = "2FA_ENABLED"
    ACTION_2FA_DISABLED = "2FA_DISABLED"
    ACTION_PLAYBOOK_CREATED = "PLAYBOOK_CREATED"
    ACTION_PLAYBOOK_UPDATED = "PLAYBOOK_UPDATED"
    ACTION_PLAYBOOK_DELETED = "PLAYBOOK_DELETED"
    ACTION_USER_CREATED = "USER_CREATED"
    ACTION_RATE_LIMITED = "RATE_LIMITED"

    @staticmethod
    def log(user: str | None, action: str, resource: str | None, ip_address: str, result: str = "success", details: str = None):
        """
        Log an audit event to the database.
        
        Args:
            user: Username performing the action (None if unauthenticated)
            action: Type of action (use constants above)
            resource: Resource being accessed/modified
            ip_address: Client IP address
            result: 'success' or 'failure'
            details: Optional additional details
        """
        try:
            engine = create_engine(settings.DATABASE_URL)
            query = text("""
                INSERT INTO audit_logs (timestamp, username, action, resource, ip_address, result, details)
                VALUES (:ts, :user, :action, :resource, :ip, :result, :details)
            """)
            
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(query, {
                        "ts": datetime.now(timezone.utc),
                        "user": user or "anonymous",
                        "action": action,
                        "resource": resource,
                        "ip": ip_address,
                        "result": result,
                        "details": details
                    })
            
            logger.info(f"AUDIT: [{action}] User: {user or 'anonymous'}, IP: {ip_address}, Result: {result}")
            
        except Exception as e:
            # Never let audit logging crash the application
            logger.error(f"Failed to write audit log: {e}")

# Singleton instance
audit = AuditLogger()
