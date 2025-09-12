<div align="center">

# 🤖 Log Anomaly Detection System with AI-Powered SOC Assistance

**A real-time, hybrid machine learning SIEM designed to detect known and unknown threats, enriched with explainable AI and automated response capabilities.**

</div>

<p align="center">
  <img src="https-placeholder-for-your-dashboard.gif" alt="Animated Demo of the Dashboard" width="90%"/>
  </p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"/>
  <img src="https://img.shields.io/badge/FastAPI-0.103-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/TensorFlow-2.13-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" alt="TensorFlow"/>
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/RabbitMQ-3.12-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white" alt="RabbitMQ"/>
  <img src="https://img.shields.io/badge/Redis-7.2-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT"/>
</p>

---

## ✨ Overview

This project is a comprehensive, real-time log anomaly detection system designed to function as the core of a modern Security Operations Center (SOC). It ingests and analyzes system logs to identify known and unknown security threats using a sophisticated **hybrid machine learning approach**. The system is coupled with a dynamic web-based dashboard for live monitoring, threat hunting, and in-depth log analysis, turning raw data into actionable intelligence.

---

## 🎯 Key Features

| Feature | Description |
| :--- | :--- |
| 🧠 **Hybrid ML Engine** | Combines **supervised**, **unsupervised (Autoencoder)**, and **sequential (LSTM)** models to detect a wide range of threats, from known patterns to novel and behavioral anomalies. |
| ⚡ **Real-Time Processing** | A decoupled architecture using **RabbitMQ** as a high-throughput message queue ensures resilient and scalable log ingestion without data loss. |
| 📊 **Interactive Dashboard** | A modern web UI built with **FastAPI** and vanilla JavaScript for live log streaming, alert management, interactive charting, and a geographic threat map. |
| 🤖 **Explainable AI (XAI)** | Integrated **LIME** to provide human-readable explanations for *why* a specific log was flagged as anomalous, building trust and aiding analyst investigations. |
| 🌍 **Threat Intelligence** | Automatically enriches logs containing IP addresses with real-time data from **AbuseIPDB**, providing immediate context on malicious actors. |
| 🗺️ **MITRE ATT&CK Mapping** | Automatically maps detected anomalies to the corresponding **MITRE ATT&CK** tactics and techniques, standardizing alert data. |
| 🔄 **Automated Model Retraining** | Implements an MLOps feedback loop where an analyst's reviewed logs are used to automatically retrain and improve the ML models over time. |
| 🔐 **Robust Security** | Features a secure login system with password hashing and end-to-end **Two-Factor Authentication (2FA)**. |

---

## 🏗️ System Architecture

The system is designed with a decoupled, asynchronous architecture to ensure scalability and resilience. The diagram below illustrates the flow of data from ingestion to presentation.

```mermaid
graph TD
    subgraph "Log Sources"
        A[📄 Log Files]
        B[ jurnalctl]
    end

    subgraph "Ingestion & Queuing"
        C[🐍 Monitor.py] --> D{🐇 RabbitMQ};
    end

    subgraph "Core Processing Engine"
        E[🧠 Worker.py];
        F[🧠 Supervised Model];
        G[🧠 Unsupervised Model];
        H[🧠 LSTM Model];
        I[⚡ Redis];
        J[🐘 PostgreSQL];
        K[🌐 Threat Intel API];
    end

    subgraph "Presentation & API Layer"
        L[🚀 FastAPI App];
        M[💻 Web UI];
    end

    A --> C;
    B --> C;
    D --> E;
    E -- uses --> F;
    E -- uses --> G;
    E -- uses --> H;
    E -- reads/writes --> I;
    E -- reads/writes --> J;
    E -- enriches with --> K;
    E -- sends results to --> L;
    L -- provides data to --> M;
    M -- sends real-time updates via WebSocket --> M;

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#ccf,stroke:#333,stroke-width:2px
    style E fill:#9f9,stroke:#333,stroke-width:2px
    style M fill:#fcf,stroke:#333,stroke-width:2px
```

---

## 🛠️ Tech Stack

| Category | Technology |
| :--- | :--- |
| **Backend** | Python, FastAPI, TensorFlow/Keras, Scikit-learn, SQLAlchemy, SentenceTransformers |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (Modular), Chart.js, Leaflet.js |
| **Infrastructure** | RabbitMQ (Message Queue), Redis (Session Store), PostgreSQL (Database) |
| **Deployment** | Honcho (Process Manager), Uvicorn (ASGI Server) |
| **Testing** | Pytest |

---

## 🚀 Setup and Installation

### Prerequisites
* Python 3.10+
* RabbitMQ Server
* Redis Server
* PostgreSQL Server
* An API key from [AbuseIPDB](https://www.abuseipdb.com/) (optional, for threat intelligence)

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd log-anomaly-detector
```

### 2. Set Up the Python Environment
```bash
python -m venv venv-s
source venv-s/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a file named `.env` in the project root. Use the example below as a template and fill in your values.

<details>
<summary><strong>Click to see .env.example content</strong></summary>

```ini
# .env.example
# Security Settings
SECRET_KEY="<generate_a_strong_random_secret_key_e.g.,_using_openssl_rand_-hex_32>"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Infrastructure Settings
RABBITMQ_HOST="localhost"
DASHBOARD_URL="[http://127.0.0.1:8000](http://127.0.0.1:8000)"
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0
DATABASE_URL="postgresql://user:password@localhost/logdb"

# Model & Session Settings
SESSION_TIMEOUT_SECONDS=1800
SEQUENCE_LEN=20
SIMILARITY_THRESHOLD=0.95

# Log File Paths (comma-separated, can be absolute or relative)
LOG_FILES_STR="/var/log/auth.log,/var/log/pacman.log,/var/log/Xorg.0.log"

# External APIs (Optional)
ABUSEIPDB_API_KEY=""
```
</details>

### 4. Database Setup
Ensure your PostgreSQL server is running. Create a database and user matching the `DATABASE_URL` in your `.env` file. You will need to manually create the tables based on the models.

### 5. Download GeoIP Database
Download the free GeoLite2 City database from MaxMind and place the `GeoLite2-City.mmdb` file in the `geoip/` directory.

---

## ▶️ Running the Application

Use the provided shell script to start all services (Web App, Worker, and Monitor) using Honcho. The script requires `sudo` access for the monitor to read system log files.

```bash
./run.sh
```
Access the dashboard at **http://127.0.0.1:8000**.

---

## 🖼️ Gallery

<p align="center">
  <img src="path/to/screenshot1.png" alt="Main Dashboard" width="45%"/>
  <img src="path/to/screenshot2.png" alt="Log Review Interface" width="45%"/>
  <br/>
  <img src="path/to/screenshot3.png" alt="Threat Map" width="45%"/>
  <img src="path/to/screenshot4.png" alt="Timeline Modal" width="45%"/>
</p>

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
