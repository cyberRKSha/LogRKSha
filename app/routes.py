from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import pandas as pd
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Read real_log.csv to get stats
    df = pd.read_csv("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv")
    total_logs = len(df)
    normal_count = len(df[df['label'] == 0])
    anomaly_count = len(df[df['label'] == 1])
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_logs": total_logs,
        "normal_count": normal_count,
        "anomaly_count": anomaly_count,
        "last_updated": last_updated
    })
