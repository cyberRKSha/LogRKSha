from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import pandas as pd
from datetime import datetime

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
def log_dim(msg): print(f"\033[90m{msg}\033[0m")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# @router.get("/", response_class=HTMLResponse)
# async def dashboard(request: Request):
#     # Read real_log.csv to get stats
#     df = pd.read_csv("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv")
#     total_logs = len(df)
#     normal_count = len(df[df['label'] == 0])
#     anomaly_count = len(df[df['label'] == 1])
#     last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     return templates.TemplateResponse("dashboard.html", {
#         "request": request,
#         "total_logs": total_logs,
#         "normal_count": normal_count,
#         "anomaly_count": anomaly_count,
#         "last_updated": last_updated
#     })

# In app/routes.py, REPLACE the dashboard function

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):

    total_logs, normal_count, anomaly_count = 0, 0, 0
    real_log_path = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

    try:
        # Load stats from the reviewed log file
        df = pd.read_csv(real_log_path)
        df.dropna(subset=['label'], inplace=True) # Ensure label column has no empty values
        total_logs = len(df)
        # Ensure label is treated as integer/float for comparison
        df['label'] = pd.to_numeric(df['label'], errors='coerce')
        normal_count = len(df[df['label'] == 0])
        anomaly_count = len(df[df['label'] == 1])
    except FileNotFoundError:
        log_info(f"'{real_log_path}' not found. Starting with zero stats.")
    except Exception as e:
        log_error(f"Error reading real_log.csv: {e}")

    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_logs": total_logs,
        "normal_count": normal_count,
        "anomaly_count": anomaly_count,
        "last_updated": last_updated
    })

# # ADD this function to the end of routes.py
# @router.get("/api/historical-trends")
# async def get_historical_trends(interval: str = 'H'):

#     try:
#         df = pd.read_csv("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv")
#         df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
#         df.dropna(subset=['timestamp'], inplace=True)
#         df.set_index('timestamp', inplace=True)

#         # Resample to get total logs and anomaly counts
#         total_logs = df['label'].resample(interval).count()
#         anomaly_logs = df[df['label'] == 1]['label'].resample(interval).count()

#         trends_df = pd.DataFrame({'total': total_logs, 'anomalies': anomaly_logs}).fillna(0)
#         trends_df.reset_index(inplace=True)
#         trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')

#         return trends_df.to_dict(orient='records')
#     except FileNotFoundError:
#         return []





# In app/routes.py, REPLACE the existing /api/historical-trends function

@router.get("/api/historical-trends")
async def get_historical_trends(interval: str = 'h'):

    real_log_path = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"
    try:
        df = pd.read_csv(real_log_path)

        # Drop rows where timestamp is missing, which can cause errors
        df.dropna(subset=['timestamp'], inplace=True)
        if df.empty:
            return []

        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Remove any rows that failed to parse
        df.dropna(subset=['timestamp'], inplace=True)
        if df.empty:
            log_warning("No valid timestamps found in real_log.csv after parsing.")
            return []

        df.set_index('timestamp', inplace=True)

        df['label'] = pd.to_numeric(df['label'], errors='coerce')
        anomaly_logs = df[df['label'] == 1]['label'].resample(interval).count()

        # Create a DataFrame from the resampled data
        trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
        trends_df.reset_index(inplace=True)
        # Format the timestamp for clean display on the chart's x-axis
        trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')

        return trends_df.to_dict(orient='records')

    except FileNotFoundError:
        log_warning(f"'{real_log_path}' not found for historical trends.")
        return []
    except Exception as e:
        log_error(f"An error occurred while generating historical trends: {e}")
        return []
    



