from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import routes, websocket
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

# --- DYNAMIC PATH CONFIGURATION ---
# This makes the paths work correctly no matter where you run the script from.
current_dir = Path(__file__).parent
static_path = current_dir / "static"
templates_path = current_dir / "templates"

app = FastAPI()

# @app.exception_handler(HTTPException)
# async def http_exception_handler(request: Request, exc: HTTPException):
#     if exc.status_code == status.HTTP_401_UNAUTHORIZED:
#         # If a page is protected and the user is not logged in, redirect to the login page
#         return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
#     # Re-raise other HTTP exceptions
#     raise exc

# Mount the static files directory using the absolute path
app.add_middleware(SessionMiddleware, secret_key="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7") 
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include the routers from your other files
app.include_router(routes.router)
app.include_router(websocket.router)
