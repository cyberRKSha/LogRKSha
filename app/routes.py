# from fastapi import APIRouter, Request
# from fastapi.templating import Jinja2Templates
# from fastapi.responses import HTMLResponse
# import pandas as pd
# from datetime import datetime

# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
# def log_dim(msg): print(f"\033[90m{msg}\033[0m")

# router = APIRouter()
# templates = Jinja2Templates(directory="app/templates")

# @router.get("/", response_class=HTMLResponse)
# async def dashboard(request: Request):

#     total_logs, normal_count, anomaly_count = 0, 0, 0
#     real_log_path = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

#     try:
#         # Load stats from the reviewed log file
#         df = pd.read_csv(real_log_path)
#         df.dropna(subset=['label'], inplace=True) # Ensure label column has no empty values
#         total_logs = len(df)
#         # Ensure label is treated as integer/float for comparison
#         df['label'] = pd.to_numeric(df['label'], errors='coerce')
#         normal_count = len(df[df['label'] == 0])
#         anomaly_count = len(df[df['label'] == 1])
#     except FileNotFoundError:
#         log_info(f"'{real_log_path}' not found. Starting with zero stats.")
#     except Exception as e:
#         log_error(f"Error reading real_log.csv: {e}")

#     last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     return templates.TemplateResponse("dashboard.html", {
#         "request": request,
#         "total_logs": total_logs,
#         "normal_count": normal_count,
#         "anomaly_count": anomaly_count,
#         "last_updated": last_updated
#     })

# @router.get("/api/historical-trends")
# async def get_historical_trends(interval: str = 'h'):

#     real_log_path = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"
#     try:
#         df = pd.read_csv(real_log_path)

#         # Drop rows where timestamp is missing, which can cause errors
#         df.dropna(subset=['timestamp'], inplace=True)
#         if df.empty:
#             return []

#         df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

#         # Remove any rows that failed to parse
#         df.dropna(subset=['timestamp'], inplace=True)
#         if df.empty:
#             log_warning("No valid timestamps found in real_log.csv after parsing.")
#             return []

#         df.set_index('timestamp', inplace=True)

#         df['label'] = pd.to_numeric(df['label'], errors='coerce')
#         anomaly_logs = df[df['label'] == 1]['label'].resample(interval).count()

#         # Create a DataFrame from the resampled data
#         trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
#         trends_df.reset_index(inplace=True)
#         # Format the timestamp for clean display on the chart's x-axis
#         trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')

#         return trends_df.to_dict(orient='records')

#     except FileNotFoundError:
#         log_warning(f"'{real_log_path}' not found for historical trends.")
#         return []
#     except Exception as e:
#         log_error(f"An error occurred while generating historical trends: {e}")
#         return []
    

































































# app/routes.py (Updated for Database Integration)
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import pandas as pd
from datetime import datetime
import sqlite3
import os

# --- Configuration ---
# This path should point to the root of your project's Linux folder
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")

# --- Logging Helpers (Optional but good practice) ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")

router = APIRouter()
# This assumes your templates are in an 'app/templates' directory
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Renders the main dashboard, fetching initial statistics
    directly from the SQLite database.
    """
    total_logs, normal_count, anomaly_count = 0, 0, 0
    
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DATABASE_FILE)
        
        # Query the database to get all HUMAN-REVIEWED logs.
        # We only want to show stats for logs that have been validated.
        # The 'final_label' is the ground truth after your review.
        query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Calculate stats using the DataFrame from the database
            total_logs = len(df)
            # Count where the final, reviewed label is 0 (normal)
            normal_count = df[df['final_label'] == 0].shape[0]
            # Count where the final, reviewed label is 1 (anomaly)
            anomaly_count = df[df['final_label'] == 1].shape[0]
            
        log_info(f"Loaded initial stats from database: Total={total_logs}, Normal={normal_count}, Anomaly={anomaly_count}")

    except Exception as e:
        log_error(f"Could not read from database to get stats: {e}")
        # The dashboard will load with zeros if the database can't be read

    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_logs": total_logs,
        "normal_count": normal_count,
        "anomaly_count": anomaly_count,
        "last_updated": last_updated
    })

@router.get("/api/historical-trends")
async def get_historical_trends(interval: str = 'h'):
    """
    Fetches historical anomaly counts from the database for charts.
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        # Query for timestamps of reviewed anomalies
        query = "SELECT timestamp FROM logs WHERE is_reviewed = 1 AND final_label = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return []

        # Convert timestamp strings to datetime objects for resampling
        # df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
        df.set_index('timestamp', inplace=True)

        # Count anomalies per time interval (e.g., per hour 'h')
        anomaly_logs = df.resample(interval).size()

        trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
        trends_df.reset_index(inplace=True)
        trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')

        return trends_df.to_dict(orient='records')

    except Exception as e:
        log_error(f"Error generating historical trends: {e}")
        return []
