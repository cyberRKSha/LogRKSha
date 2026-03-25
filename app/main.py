from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.websocket import router as websocket_router
from app.api import auth, dashboard, review, playbooks
from app.log_config import setup_logging
from app.rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

setup_logging()

app = FastAPI(title="Log Anomaly Detector API")

# Attach limiter to app state for use in routes
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Mount the static files directory using the absolute path
app.add_middleware(SessionMiddleware, secret_key="settings.SECRET_KEY") 

# Secure headers middleware (small, safe-by-default headers)
class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        # Only add headers to HTTP responses
        if isinstance(resp, Response):
            resp.headers['X-Frame-Options'] = 'DENY'
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            resp.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
            resp.headers['Permissions-Policy'] = 'geolocation=()'
            # Add HSTS in production only (only when you serve over HTTPS)
            # resp.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
            resp.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' ws:; img-src 'self' data: https://*.basemaps.cartocdn.com https://*.tile.openstreetmap.org;"
        return resp

app.add_middleware(SecureHeadersMiddleware)

app.mount("/static", StaticFiles(directory=settings.STATIC_PATH), name="static")
app.mount("/node_modules", StaticFiles(directory=settings.PROJECT_ROOT / "node_modules"), name="node_modules")
# Include the routers from your other files
# app.include_router(routes.router)
# app.include_router(websocket.router)
app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(review.router)
app.include_router(playbooks.router)
app.include_router(websocket_router)

# Import and include the ingest router
from app.api import ingest
app.include_router(ingest.router)

from app.api import security
app.include_router(security.router)

from app.api import benchmark
app.include_router(benchmark.router)

from app.api import ai
app.include_router(ai.router)

from app.api import users
app.include_router(users.router)

from app.api import cases
app.include_router(cases.router)