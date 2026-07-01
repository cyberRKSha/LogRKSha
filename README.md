# LogRKSha

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/TensorFlow-2.15-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" alt="TensorFlow"/>
  <img src="https://img.shields.io/badge/PostgreSQL-14-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Redis-7.2-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/RabbitMQ-3.12-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white" alt="RabbitMQ"/>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT"/></a>
</p>

A production-grade, hybrid machine learning SIEM that detects **known threats** through a deterministic Sigma rules engine and **unknown behavioral anomalies** through a multi-model ML pipeline — SentenceTransformers, Autoencoders, and LSTMs — running in parallel. LogRKSha unifies system logs (Syslog, Journald) and network telemetry (Zeek) into a single analysis pipeline, enriched with MITRE ATT&CK mapping, real-time threat intelligence, automated response playbooks, and generative AI-assisted investigation.

<img width="1919" height="1080" alt="LogRKSha Dashboard" src="https://github.com/user-attachments/assets/0fea9130-e9d8-42b4-8f18-bca8d6ff5ffd" />
<img width="1832" height="1010" alt="LogRKSha Alerts" src="https://github.com/user-attachments/assets/690ba889-4b57-4256-96c7-3b0e257e0877" />

---

<details>
  <summary><b>📑 Table of Contents</b></summary>

  - [Core Features](#-core-features)
    - [Ingestion & Brokering](#domain-1-ingestion--brokering)
    - [Hybrid Detection Engine](#domain-2-hybrid-detection-engine)
    - [Real-Time Backend](#domain-3-real-time-backend)
    - [Automated Response](#domain-4-automated-response)
  - [Architecture & Data Flow](#-architecture--data-flow)
  - [Quick Start & Installation](#-quick-start--installation)
  - [Configuration Reference](#-configuration-reference)
  - [Dashboard & Visualization](#-dashboard--visualization)
  - [Authentication & Access Control](#-authentication--access-control)
  - [Research & Baselines](#-research--baselines)
  - [Technology Stack](#-technology-stack)
  - [Project Structure](#-project-structure)
  - [Testing & Simulation](#-testing--simulation)
  - [Contributing](#-contributing)
  - [License](#-license)

</details>

---

<details>
  <summary><b>⚡ Core Features</b></summary>

  ### Domain 1: Ingestion & Brokering

  The monitor process (`scripts/monitor.py`) is the system's ears — a multi-threaded daemon that tails every configured log source and ships lines to the processing pipeline via HTTP batching.

  - **Syslog & Journald**: A dedicated thread reads from the systemd journal in real-time using `python-systemd`, capturing all kernel, service, and authentication events. Flat log files (`/var/log/auth.log`, `/var/log/kern.log`, etc.) are monitored using `watchdog` filesystem observers that trigger on `inotify` modification events.
  - **Zeek Network Logs**: Zeek's tab-separated logs (`conn.log`, `dns.log`, `http.log`, `ssl.log`, `x509.log`, `weird.log`, `notice.log`, `files.log`) are ingested through both a `watchdog` observer and a parallel polling thread (3-second interval) for resilience. A periodic health check thread monitors Zeek file modification times every 5 minutes.
  - **HTTP Log Shipper**: Ingested lines are batched (up to 50 per request) and shipped to the FastAPI ingest endpoint (`/api/ingest/logs`) over HTTP with API key authentication. This decouples the monitor from the processing worker and enables remote log collection.
  - **RabbitMQ Durable Queues**: The ingest endpoint pushes each log into a persistent RabbitMQ queue (`log_queue`, `durable=True`) with `delivery_mode=2` (persistent messages). The worker process pulls from this queue with `prefetch_count=1` and manual acknowledgements, ensuring zero message loss even during crashes.
  - **Deduplication**: Every log line is SHA-256 hashed. Known hashes are stored on disk (`kwnhashes.txt`) and checked before processing, eliminating redundant analysis.

  ---

  ### Domain 2: Hybrid Detection Engine

  Every log line passes through multiple detection layers in the worker (`scripts/worker.py`). For standard syslog, all layers run in sequence. For Zeek network logs, a specialized engine handles analysis independently.

  **Sigma Rule Engine (Deterministic)**
  
  A custom parser (`scripts/sigma_engine.py`) loads and matches YAML Sigma rules against incoming logs. Supports custom rules with priority loading, keyword extraction from detection blocks, field-level conditions, and category tagging. Rules are organized by platform (Linux, Network, Web) and sourced from the [SigmaHQ](https://github.com/SigmaHQ/sigma) repository.

  ```yaml
  # Example: Custom rule for SSH brute force detection
  title: SSH Brute Force Attempt
  status: stable
  level: high
  detection:
    selection:
      - "Failed password"
      - "authentication failure"
    condition: selection
  ```

  **Semantic Analysis (SentenceTransformer + SGD Classifier)**
  
  Log lines are encoded into 384-dimensional dense vector embeddings using a BERT-based SentenceTransformer (`all-MiniLM-L6-v2`). An SGD classifier trained on labeled data provides supervised anomaly classification, with risk scores derived from prediction confidence.

  **Unsupervised Anomaly Detection (TensorFlow Autoencoder)**
  
  A Keras autoencoder learns the "normal" distribution of log embeddings during training. At inference, logs with high reconstruction error — patterns the model has never seen — are flagged as `Novelty Detected`. This is the primary mechanism for **zero-day detection**.

  **Behavioral Sequence Analysis (LSTM)**
  
  Rolling 20-step session windows are maintained in Redis, keyed by IP address, username, or process ID. An LSTM model evaluates whether the current sequence of actions is consistent with historical patterns. Catches lateral movement, privilege escalation, and brute-force sequences that appear normal in isolation.

  **Zeek Network Analysis Engine**
  
  A dedicated ML engine (`scripts/zeek_ml_engine.py`) with specialized analyzers per protocol:

  | Protocol | Analysis Capabilities |
  |:--|:--|
  | DNS | DGA detection via Shannon entropy, query length analysis, suspicious TLD identification |
  | Connection | Port scan detection, long-duration connection flagging, connection state scoring |
  | HTTP | SQL injection patterns, XSS detection, path traversal checks, suspicious user-agent scoring |
  | SSL | Expired certificate detection, weak cipher identification, self-signed cert flagging |
  | Alerts | Zeek's own `weird.log` and `notice.log` parsing with risk scoring |

  **Post-Detection Enrichment**

  - **MITRE ATT&CK Mapping**: Every anomaly is matched against ATT&CK tactics and techniques via keyword-based rule matching (`attack_mapping.json`).
  - **Explainable AI (LIME)**: Per-log feature importance breakdowns are generated using LIME, rendered as visual bar charts in the dashboard so analysts can see exactly which tokens contributed to the classification.
  - **AbuseIPDB Threat Intelligence**: Anomalous logs containing IP addresses trigger real-time reputation checks. Results (abuse confidence score, ISP, country, total reports) are cached in Redis for 24 hours to minimize API calls.
  - **GeoIP Resolution**: MaxMind GeoIP2 database maps source and destination IPs to geographic coordinates for the interactive threat map.

  <img width="1841" height="922" alt="Detection Results" src="https://github.com/user-attachments/assets/1cd6e6df-be0d-4e3b-9b9a-f75b0cfd73de" />
  <img width="1065" height="1043" alt="LIME Explanations" src="https://github.com/user-attachments/assets/adad4eff-6bae-49d2-93d4-c0b28c6f4ae1" />
  <img width="911" height="379" alt="MITRE Mapping" src="https://github.com/user-attachments/assets/11cb541b-38ec-4139-a0b1-61ab1ca48239" />

  ---

  ### Domain 3: Real-Time Backend

  The FastAPI backend (`app/main.py`) serves the analyst dashboard, the REST API, and the live event stream.

  - **Async Routers**: 11 modular API routers cover authentication, dashboard queries, alert management, case management, playbooks, AI insights, user management, security (honeytokens, 2FA), log review, benchmarking, and external log ingestion.
  - **WebSocket Broadcasting**: A connection manager (`app/websocket.py`) maintains a set of connected analyst clients. Every processed log, alert, and Sigma match is broadcast in real time — new detections appear in the dashboard instantly with no polling.
  - **Redis Caching**: Threat intelligence results, LLM responses, and session sequences are cached in Redis with configurable TTLs. IP reputation lookups use a 24-hour cache window; LLM responses default to 1 hour.
  - **PostgreSQL + TimescaleDB**: All logs, alerts, cases, playbooks, users, honeytokens, model metrics, and audit trails are stored in PostgreSQL. Schema is managed by Alembic migrations (8 versions tracked). Optional dual-write to Elasticsearch for full-text search at scale.
  - **Rate Limiting**: Login and API endpoints are rate-limited via `slowapi` (5 requests/minute/IP on auth endpoints) to prevent brute-force attacks.
  - **Secure Headers Middleware**: Every response includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, and a restrictive `Content-Security-Policy`.

  ---

  ### Domain 4: Automated Response

  **SOAR Playbooks**
  
  Automated response playbooks execute defensive actions when alert conditions are met, without analyst intervention.

  Supported actions:
  - `block_ip_ufw` — Block malicious IPs at the firewall level with configurable duration
  - `send_slack_alert` — Real-time notifications to SOC team channels via webhook
  - `send_email_alert` — Email notifications with configurable recipients
  - `create_case` — Automatically create investigation cases from high-severity alerts
  - `run_script` — Execute custom response scripts

  Playbook triggers use JSON condition definitions with operators (`>=`, `<=`, `==`, `!=`, `contains`, `regex`):

  ```json
  {
    "name": "Block High-Risk External IPs",
    "trigger_conditions": {
      "risk_score": {"operator": ">=", "value": 0.85}
    },
    "actions": [
      {"action": "block_ip_ufw", "duration_hours": 24},
      {"action": "send_slack_alert", "channel": "#soc-critical"}
    ],
    "is_active": true
  }
  ```

  **LLM-Assisted Threat Intelligence**
  
  LogRKSha integrates with 6 LLM providers (Gemini, Groq, Mistral, OpenRouter, Together AI, Ollama) with automatic failover, rate-limit cooldowns, and Redis-cached responses:
  
  - **Incident Summarization** — Executive summaries of alert clusters
  - **Trend Analysis** — Natural language explanation of anomaly spikes
  - **Remediation Suggestions** — Context-aware response steps based on alert context, threat intel, and MITRE mapping
  - **Playbook Generation** — Describe desired behavior in natural language; the system generates structured JSON playbooks

  See [LLM_SETUP.md](LLM_SETUP.md) for provider configuration.

  <img width="1734" height="949" alt="Playbooks" src="https://github.com/user-attachments/assets/eb125454-e40d-4e6c-baa8-d5a394df0099" />
  <img width="1737" height="823" alt="Playbook Actions" src="https://github.com/user-attachments/assets/1f17ccc9-79ff-46a7-94d6-c68e0ed5e475" />
  <img width="1735" height="502" alt="Playbook Triggers" src="https://github.com/user-attachments/assets/d8309fdb-4aa8-49e1-ba81-7e1a770bc747" />
  <img width="1832" height="942" alt="AI Integration" src="https://github.com/user-attachments/assets/b0663ed9-8352-46db-94fe-359d307ce9bf" />

  **Honeytoken Deception**
  
  Deploy decoy credentials (AWS keys, database credentials, API tokens) into monitored log paths. When a honeytoken is accessed, the worker forces a risk score of `1.0`, generates a high-severity alert, and triggers all associated playbooks. Honeytokens are managed through the Security dashboard with full create/delete/status controls.

  **Case Management**

  Investigation cases group related alerts into a single tracked unit:
  - Full CRUD with alert linking/unlinking
  - Priority levels: Low, Medium, High, Critical
  - Status workflow: Open → In Progress → Resolved → Closed
  - Analyst assignment and audit trail

</details>

---

<details>
  <summary><b>🏗️ Architecture & Data Flow</b></summary>

  ![Architecture Diagram](./docs/architecture.png)

  ```mermaid
  graph TD
      subgraph "Ingestion Layer"
          A[System Logs - Journald/Syslog]
          B[Network Logs - Zeek]
          C[Monitor Process]
      end

      subgraph "Message Bus"
          D{RabbitMQ}
      end

      subgraph "Core Processing - Worker"
          E[Worker - Decision Engine]

          subgraph "Detection Modules"
              F[Sigma Rule Engine]
              G[Semantic ML - Autoencoder]
              H[Sequential ML - LSTM]
              Z[Zeek ML Engine]
          end

          I[Redis - Session Cache]
          J[PostgreSQL - Storage]
          K[AbuseIPDB - Threat Intel]
      end

      subgraph "Response and UI"
          L[FastAPI Backend]
          M[SOC Dashboard]
          N[Playbooks - UFW / Slack]
      end

      A --> C
      B --> C
      C --> D
      D --> E

      E --> F
      E --> G
      E --> H
      E --> Z

      E <--> I
      E --> J
      E <--> K

      E --> L
      L --> M
      E --> N
  ```

  ### How a Log Travels from `/var/log` to the Browser

  1. **Tail** — The `monitor.py` daemon detects a new line in a watched log file via `watchdog` inotify events (or systemd journal reader for journald, or polling for Zeek logs).
  2. **Queue Locally** — The line is placed into a thread-safe `queue.Queue()` with its source filename.
  3. **Ship via HTTP** — The HTTP shipper thread drains the queue in batches of up to 50, sending them as a JSON payload to `POST /api/ingest/logs` with an `X-API-Key` header.
  4. **Enqueue in RabbitMQ** — The ingest endpoint checks for honeytokens and publishes each log as a persistent message to the `log_queue` durable queue.
  5. **Consume & Deduplicate** — The `worker.py` process pulls messages one at a time (`prefetch_count=1`), SHA-256 hashes them, and skips any previously seen log.
  6. **Detect** — The log passes through: Sigma rule matching → SentenceTransformer embedding → SGD supervised classification → Autoencoder reconstruction error → LSTM sequence risk scoring. For Zeek logs, the specialized network engine handles analysis instead.
  7. **Enrich** — If anomalous, the worker extracts IPs, queries AbuseIPDB (Redis-cached), maps to MITRE ATT&CK, and generates LIME explanations.
  8. **Store** — Results are written to PostgreSQL (with optional Elasticsearch dual-write). If anomalous, an alert row is created in the `alerts` table.
  9. **Respond** — Active playbooks are evaluated against the alert. Matching playbooks execute their actions (UFW block, Slack notification, case creation).
  10. **Broadcast** — The full payload (log, verdict, risk score, alert info, MITRE data) is `POST`ed to the FastAPI WebSocket broadcaster, which pushes it to every connected analyst dashboard in real time.

</details>

---

<details>
  <summary><b>🚀 Quick Start & Installation</b></summary>

  ### Prerequisites

  | Requirement | Notes |
  |:--|:--|
  | **Python 3.11+** | Developed and tested on 3.11 |
  | **Docker & Docker Compose** | For infrastructure services (PostgreSQL, Redis, RabbitMQ) |
  | **libsystemd-dev + pkg-config** | Required for systemd journal access on Linux |
  | **Zeek** | Optional — only required for network log analysis |
  | **sudo privileges** | Required for reading system logs and managing UFW rules |

  ### 1. Clone and Set Up the Environment

  ```bash
  git clone https://github.com/cyberRKSha/LogRKSha.git
  cd LogRKSha

  # Install system dependencies
  sudo apt update && sudo apt install -y libsystemd-dev pkg-config

  # Create and activate Python virtual environment
  python3.11 -m venv venv-s
  source venv-s/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  ```

  ### 2. Configure Environment Variables

  ```bash
  cp .env.example .env
  # Edit .env and fill in required values (see Configuration Reference section)
  ```

  ### 3. Boot Infrastructure

  ```bash
  docker compose up -d
  ```

  This starts **TimescaleDB** (PostgreSQL), **RabbitMQ** (with management UI), and **Redis**.

  ### 4. Apply Database Migrations

  ```bash
  alembic upgrade head
  ```

  ### 5. Create the First Admin User

  ```bash
  python scripts/create_user.py
  ```

  ### 6. Start All Services

  ```bash
  # Option A: Using Honcho (starts worker + monitor from Procfile)
  ./run.sh

  # Option B: Start the web server separately
  python run.py
  ```

  The web server starts at **http://127.0.0.1:8000**. The `run.sh` script activates the virtual environment and uses Honcho to start both the detection worker and the log monitor. You may be prompted for your sudo password (the monitor requires root to access system logs).

</details>

---

<details>
  <summary><b>⚙️ Configuration Reference</b></summary>

  All configuration is managed through `.env` and loaded via Pydantic Settings (`app/config.py`).

  | Variable | Required | Description |
  |:--|:--:|:--|
  | `SECRET_KEY` | ✅ | JWT signing key — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
  | `ALGORITHM` | ✅ | JWT algorithm (default: `HS256`) |
  | `DATABASE_URL` | ✅ | PostgreSQL connection string (e.g., `postgresql://user:pass@localhost:5432/dbname`) |
  | `RABBITMQ_HOST` | ✅ | RabbitMQ host (default: `localhost`) |
  | `REDIS_HOST` | ✅ | Redis host (default: `localhost`) |
  | `REDIS_PORT` | ✅ | Redis port (default: `6379`) |
  | `LOG_FILES_STR` | ✅ | Comma-separated list of log files to monitor |
  | `DASHBOARD_URL` | ✅ | URL of the FastAPI server (default: `http://127.0.0.1:8000`) |
  | `SEQUENCE_LEN` | ✅ | LSTM sequence window length (default: `20`) |
  | `SIMILARITY_THRESHOLD` | ✅ | Embedding similarity threshold (default: `0.95`) |
  | `ABUSEIPDB_API_KEY` | — | AbuseIPDB API key for threat intel enrichment |
  | `SLACK_WEBHOOK_URL` | — | Slack webhook for playbook notifications |
  | `GEMINI_API_KEY` | — | Google Gemini key (see [LLM_SETUP.md](LLM_SETUP.md)) |
  | `GROQ_API_KEY` | — | Groq key (alternative LLM provider) |
  | `LLM_DEFAULT_PROVIDER` | — | Preferred LLM provider (default: `gemini`) |
  | `ENVIRONMENT` | — | `development` or `production` |

  At least one LLM provider API key is needed to enable AI features. All listed providers offer free tiers. See [LLM_SETUP.md](LLM_SETUP.md) for all 6 supported providers.

</details>

---

<details>
  <summary><b>📊 Dashboard & Visualization</b></summary>

  The analyst dashboard is a single-page application built with vanilla JavaScript (ES6 modules) and served by FastAPI via Jinja2 templates.

  - **Real-time log feed** via WebSocket streaming — new detections appear instantly without polling
  - **Geographic threat map** using Leaflet.js and MaxMind GeoIP data, plotting attack origins on an interactive world map
  - **Alert management panel** with status transitions (New → Acknowledged → Closed), analyst notes, and case linking
  - **Interactive charts** (Chart.js): historical trend analysis, alert severity breakdowns, session risk scoring, model drift detection
  - **Log search** with full-text and field-based filtering, backed by PostgreSQL (with optional Elasticsearch integration)
  - **Training statistics** showing model performance metrics over time
  - **Model retraining** trigger directly from the dashboard (admin only)
  - **Log Review System**: DBSCAN-based cluster review for bulk labeling and manual log-by-log review for refining model accuracy

  <img width="1835" height="933" alt="Dashboard Overview" src="https://github.com/user-attachments/assets/5d8ea4d1-4192-44e1-b0f6-0a2d92a5709a" />
  <img width="1912" height="903" alt="Alert Management" src="https://github.com/user-attachments/assets/28111978-e850-4f12-961e-56c93367abd0" />
  <img width="1908" height="806" alt="Geographic Threat Map" src="https://github.com/user-attachments/assets/a8ab295f-901a-44e5-aec3-34cbd6228df2" />
  <img width="1914" height="1012" alt="Charts and Analytics" src="https://github.com/user-attachments/assets/119828ac-34df-476c-bbbe-6e93f62549ff" />

</details>

---

<details>
  <summary><b>🔐 Authentication & Access Control</b></summary>

  ### User Roles

  | Role | Dashboard | Review Logs | Cases & Alerts | User Management | Model Retraining | How to Create |
  |:--|:--:|:--:|:--:|:--:|:--:|:--|
  | **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | Initial setup / Admin API |
  | **Analyst** | ✅ | ✅ | ✅ | ❌ | ❌ | Created by Admin |
  | **Viewer** | ✅ (read-only) | ❌ | ❌ | ❌ | ❌ | Self-signup on login page |

  ### Dual-Portal Login

  - **Standard Login** — Used by Analyst and Viewer accounts
  - **Admin Portal** — Separate modal with distinct red-themed UI. Only admin-role users can authenticate; non-admin credentials are rejected. Admin accounts are blocked from using the standard login form.

  ### Two-Factor Authentication (2FA)

  - TOTP-based (Time-based One-Time Password) via `pyotp`
  - QR code enrollment compatible with Google Authenticator, Authy, and any TOTP app
  - Login with 2FA enabled generates a temporary `pre-2fa` JWT token (5-minute expiry), redirecting to code verification before issuing the full session token

  ### Security Measures

  - JWT tokens in HTTP-only, SameSite-strict cookies (secure flag in production)
  - Rate limiting on login endpoints (5 req/min/IP)
  - Password hashing via bcrypt with automatic salt generation
  - Full audit logging of all authentication events with timestamps, IPs, and outcomes
  - Self-deletion prevention for admin accounts

</details>

---

<details>
  <summary><b>🔬 Research & Baselines</b></summary>

  The `experiments/` directory contains reference implementations of established log anomaly detection papers, used to benchmark LogRKSha's hybrid approach:

  | File | Paper / Method | Description |
  |:--|:--|:--|
  | `deeplog_baseline.py` | **DeepLog** | LSTM-based log key prediction model |
  | `logbert_baseline.py` | **LogBERT** | BERT-based masked log key prediction model |
  | `evaluate.py` | Evaluation Framework | Standardized metrics comparison (accuracy, F1, precision, recall) across all approaches |
  | `hybrid_hdfs_pipeline.py` | Hybrid Pipeline | Combined autoencoder + supervised + sequence approach tested on the HDFS dataset |

  These implementations serve as performance baselines against which the hybrid detection engine is measured. Results are written to `results/` as CSV files.

</details>

---

<details>
  <summary><b>🛠️ Technology Stack</b></summary>

  | Component | Technology |
  |:--|:--|
  | Language | Python 3.11 |
  | Backend API | FastAPI (async), SQLAlchemy ORM, Pydantic |
  | Deep Learning | TensorFlow/Keras (Autoencoder, LSTM), SentenceTransformers (BERT) |
  | Classical ML | scikit-learn (SGD, IsolationForest, DBSCAN, StandardScaler) |
  | Rules Engine | Custom Sigma parser (YAML) |
  | Explainability | LIME (Local Interpretable Model-agnostic Explanations) |
  | Database | PostgreSQL 14 (TimescaleDB), Alembic migrations |
  | Cache / Sessions | Redis |
  | Message Queue | RabbitMQ |
  | Frontend | Vanilla JavaScript (ES6 modules), Chart.js, Leaflet.js |
  | Process Manager | Honcho |
  | Authentication | python-jose (JWT), pyotp (TOTP 2FA), bcrypt |
  | Threat Intel | AbuseIPDB API, MaxMind GeoIP2 |
  | Network Analysis | Zeek |
  | LLM Integration | Gemini, Groq, Mistral, OpenRouter, Together AI, Ollama |
  | Testing | pytest, GitHub Actions CI |

</details>

---

<details>
  <summary><b>📁 Project Structure</b></summary>

  ```
  LogRKSha/
  ├── app/                        # FastAPI application
  │   ├── api/                    # Route handlers (11 modules)
  │   │   ├── auth.py             # Authentication (login, 2FA, logout)
  │   │   ├── dashboard.py        # Dashboard endpoints, search, alerts, charts
  │   │   ├── cases.py            # Case management CRUD
  │   │   ├── playbooks.py        # Playbook CRUD + LLM generation
  │   │   ├── review.py           # Cluster review, manual review, noise logs
  │   │   ├── ai.py               # LLM-powered insights API
  │   │   ├── security.py         # Honeytoken management, 2FA setup
  │   │   ├── users.py            # User management (admin only)
  │   │   ├── ingest.py           # External log ingestion + RabbitMQ producer
  │   │   └── benchmark.py        # Model benchmarking
  │   ├── services/               # Business logic services
  │   │   ├── llm_service.py      # Multi-provider LLM with failover + caching
  │   │   ├── cache.py            # Redis cache wrapper
  │   │   ├── honeytoken.py       # Honeytoken detection service
  │   │   └── es_client.py        # Elasticsearch client (optional)
  │   ├── static/                 # CSS (6 files), JavaScript (16 ES6 modules), audio
  │   ├── templates/              # Jinja2 HTML templates (7 pages)
  │   ├── config.py               # Pydantic settings (loads .env)
  │   ├── db_models.py            # SQLAlchemy ORM models
  │   ├── main.py                 # FastAPI app factory + middleware
  │   ├── websocket.py            # WebSocket connection manager + broadcaster
  │   ├── auth_utils.py           # JWT creation/verification + 2FA utilities
  │   ├── audit.py                # Audit logging service
  │   └── rate_limiter.py         # Request rate limiting
  ├── scripts/                    # Background processes & utilities
  │   ├── worker.py               # Detection worker (RabbitMQ consumer, 788 lines)
  │   ├── monitor.py              # Log monitor (HTTP shipper + Zeek integration)
  │   ├── sigma_engine.py         # Sigma rule parser and matcher
  │   ├── zeek_ml_engine.py       # Zeek network log ML engine (protocol-specific)
  │   ├── playbooks.py            # Playbook action executor (UFW, Slack)
  │   ├── att_sim.py              # Attack simulation tool
  │   ├── auto_trainer.py         # Automated model retraining pipeline
  │   ├── create_user.py          # Interactive user creation utility
  │   └── validate_detection.py   # Detection validation framework
  ├── experiments/                 # Research baselines (DeepLog, LogBERT)
  ├── sigma-rules/                # Sigma detection rules (YAML, SigmaHQ)
  ├── alembic/                    # Database migration scripts (8 versions)
  ├── tests/                      # Pytest test suite (10 files)
  ├── model/                      # Trained model artifacts (gitignored)
  ├── .github/workflows/          # CI pipeline (python-ci.yml)
  ├── docker-compose.yml          # TimescaleDB, RabbitMQ, Redis
  ├── Procfile                    # Honcho process definitions
  ├── run.sh / run.py             # System launch scripts
  ├── requirements.txt            # Python dependencies
  ├── .env.example                # Environment variable template
  └── LLM_SETUP.md                # LLM provider configuration guide
  ```

</details>

---

<details>
  <summary><b>🧪 Testing & Simulation</b></summary>

  ### Running the Test Suite

  ```bash
  pytest
  ```

  The CI pipeline (`.github/workflows/python-ci.yml`) runs the full test suite on every push and pull request to `master`.

  ### Attack Simulation

  The project includes a simulation tool that generates realistic attack patterns for end-to-end validation:

  ```bash
  # Run a brute-force simulation
  python scripts/att_sim.py --scenario brute_force

  # Run a port scan simulation
  python scripts/att_sim.py --scenario port_scan
  ```

  Simulated attacks flow through the full pipeline (monitor → RabbitMQ → worker → detection → alerts) and appear in the dashboard, allowing complete validation of the detection and response system.

</details>

---

<details>
  <summary><b>🤝 Contributing</b></summary>

  Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

</details>

---

<details>
  <summary><b>📄 License</b></summary>

  This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

</details>
