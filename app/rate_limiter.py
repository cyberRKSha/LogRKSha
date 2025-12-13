# app/rate_limiter.py
"""
Rate Limiting Configuration using SlowAPI.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging

logger = logging.getLogger(__name__)

# Initialize the limiter with IP-based key function
limiter = Limiter(key_func=get_remote_address)

# Export the exception handler for use in main.py
rate_limit_exceeded_handler = _rate_limit_exceeded_handler

def get_limiter():
    """Returns the configured limiter instance."""
    return limiter
