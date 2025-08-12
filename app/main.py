from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import routes, websocket
from pathlib import Path

# --- DYNAMIC PATH CONFIGURATION ---
# This makes the paths work correctly no matter where you run the script from.
current_dir = Path(__file__).parent
static_path = current_dir / "static"
templates_path = current_dir / "templates"

app = FastAPI()

# Mount the static files directory using the absolute path
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include the routers from your other files
app.include_router(routes.router)
app.include_router(websocket.router)
