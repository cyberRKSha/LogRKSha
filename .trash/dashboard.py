# dashboard.py

import streamlit as st
import pandas as pd

LOG_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"  # updated live by monitor script

st.set_page_config("📊 Real-Time Log Viewer", layout="wide")
st.title("📄 Live Log Feed")

@st.cache_data(ttl=2)  # refresh every 2 seconds
def load_logs():
    return pd.read_csv(
        LOG_FILE,
        names=["timestamp", "source", "content", "label"]
    )

logs = load_logs()

if not logs.empty:
    # Convert label to readable text
    logs["status"] = logs["label"].apply(
    lambda x: "Anomaly" if str(x).strip() == '1' else "Normal"
    )
    
    # Apply color: red for anomaly, green for normal
    def color_row(row):
        color = "#ee0f0f" if row["status"] == "Anomaly" else "#00af00"
        return ['background-color: {}'.format(color)]*len(row)

    st.dataframe(
        logs[["timestamp", "content", "status"]]
            .style.apply(color_row, axis=1),
        use_container_width=True,
        height=600
    )
else:
    st.info("Waiting for logs... Nothing to show yet.")
