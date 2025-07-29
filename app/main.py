from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
from app import routes, websocket

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
# templates = Jinja2Templates(directory="app/templates")

# Include routes
app.include_router(routes.router)
app.include_router(websocket.router)


