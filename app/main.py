from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.websocket import router as websocket_router
from app.api import auth, dashboard, review
from app.log_config import setup_logging

setup_logging()

app = FastAPI(title="Log Anomaly Detector API")

# Mount the static files directory using the absolute path
app.add_middleware(SessionMiddleware, secret_key="settings.SECRET_KEY") 
app.mount("/static", StaticFiles(directory=settings.STATIC_PATH), name="static")

# Include the routers from your other files
# app.include_router(routes.router)
# app.include_router(websocket.router)
app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(review.router)
app.include_router(websocket_router)