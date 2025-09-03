# Real-Time Log Anomaly Detection with a Hybrid AI SIEM

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)

A full-stack, real-time log anomaly detection system that functions as a lightweight, AI-powered Security Information and Event Management (SIEM) tool. It uses a hybrid of supervised, unsupervised, and sequential machine learning models to identify and classify threats from log streams. The project includes a complete MLOps pipeline for continuous learning and a feature-rich web dashboard for threat hunting, analysis, and reporting.

---

### ✨ Live Demo (Placeholder)

![Live Demo of the Dashboard in Action](<link_to_your_demo.gif>)
*(It's highly recommended to record a short GIF of your dashboard in action and place it here.)*

---

## 🚀 The Problem & The Solution

In any modern IT infrastructure, system and application logs are generated at an overwhelming rate. Manually analyzing this data for security threats is impossible. Traditional security tools often rely on static rules that fail to detect novel, zero-day attacks.

This project solves that problem by implementing a sophisticated, multi-layered AI engine that learns the "normal" behavior of a system and flags any deviation, all while providing a powerful UI for human analysts to investigate and provide feedback, creating a continuous cycle of improvement.

---

## 🛠️ Technology Stack

| Category           | Technologies                                                                                                                                                                                                                                                                    |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Backend** | [![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)]() [![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)]() [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)]()     |
| **Frontend** | [![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)]() [![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)]() [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)]()                 |
| **Database** | [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)]() [![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)]()                                                                                              |
| **Data & ML** | [![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white)]() [![Sentence Transformers](https://img.shields.io/badge/Sentence_Transformers-3498DB?logo=huggingface&logoColor=white)]() [![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?logo=tensorflow&logoColor=white)]() [![Scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)]() |
| **Infrastructure** | [![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?logo=rabbitmq&logoColor=white)]() [![Uvicorn](https://img.shields.io/badge/Uvicorn-00B2FF?logo=python&logoColor=white)]() [![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)]()         |

---

## 📊 System Architecture & Data Flow

The system is architected as a set of decoupled microservices that communicate through a central message broker, ensuring scalability and resilience.

```mermaid
graph TD
    A[Log Sources <br> /var/log, journalctl] --> B(Monitor Agent <br> monitor.py);
    B --> C{RabbitMQ <br> Message Queue};
    C --> D[Worker <br> worker.py];
    D -- Stores Sessions --> E(Redis);
    D -- Reads Sessions --> E;
    D -- Writes Verdicts --> F(PostgreSQL Database);
    
    G[FastAPI Backend <br> app/main.py] -- Reads Data --> F;
    G -- Manages Auth --> F;
    
    H[User's Browser <br> Frontend] <-->|HTTP API / WebSockets| G;
    
    I[Human Analyst] --> H;
    I -- Reviews Logs --> H;
    H -- Sends Feedback --> G;
    
    J[Retraining Script <br> update.py] -- Reads Reviewed Logs --> F;
    J -- Saves New Models --> K[Model Storage];
    D -- Loads Models --> K;

    subgraph "Real-time Ingestion"
        A
        B
        C
    end
    
    subgraph "AI Processing Core"
        D
        E
        K
    end
    
    subgraph "Data & Application Layer"
        F
        G
        H
    end
    
    subgraph "MLOps Feedback Loop"
        I
        J
    end

Of course. A detailed README is the hallmark of a professional project and is essential for GitHub. It showcases not just the final product, but also your design thinking, architectural knowledge, and understanding of the underlying technologies.

Here is a more advanced, in-depth version of the README.md. It's structured to be a comprehensive guide for anyone visiting your repository, from a casual observer to a potential employer.

## Action: Replace Your README.md
Copy the entire markdown text below and paste it into your README.md file. It's designed to be ready for your GitHub profile.

Markdown

# Real-Time Log Anomaly Detection with a Hybrid AI SIEM

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)

A full-stack, real-time log anomaly detection system that functions as a lightweight, AI-powered Security Information and Event Management (SIEM) tool. It uses a hybrid of supervised, unsupervised, and sequential machine learning models to identify and classify threats from log streams. The project includes a complete MLOps pipeline for continuous learning and a feature-rich web dashboard for threat hunting, analysis, and reporting.

---

### ✨ Live Demo (Placeholder)

![Live Demo of the Dashboard in Action](<link_to_your_demo.gif>)
*(It's highly recommended to record a short GIF of your dashboard in action and place it here.)*

---

## 🚀 The Problem & The Solution

In any modern IT infrastructure, system and application logs are generated at an overwhelming rate. Manually analyzing this data for security threats is impossible. Traditional security tools often rely on static rules that fail to detect novel, zero-day attacks.

This project solves that problem by implementing a sophisticated, multi-layered AI engine that learns the "normal" behavior of a system and flags any deviation, all while providing a powerful UI for human analysts to investigate and provide feedback, creating a continuous cycle of improvement.

---

## 🛠️ Technology Stack

| Category           | Technologies                                                                                                                                                                                                                                                                    |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Backend** | [![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)]() [![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)]() [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)]()     |
| **Frontend** | [![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)]() [![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)]() [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)]()                 |
| **Database** | [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)]() [![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)]()                                                                                              |
| **Data & ML** | [![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white)]() [![Sentence Transformers](https://img.shields.io/badge/Sentence_Transformers-3498DB?logo=huggingface&logoColor=white)]() [![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?logo=tensorflow&logoColor=white)]() [![Scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)]() |
| **Infrastructure** | [![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?logo=rabbitmq&logoColor=white)]() [![Uvicorn](https://img.shields.io/badge/Uvicorn-00B2FF?logo=python&logoColor=white)]() [![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)]()         |

---

## 📊 System Architecture & Data Flow

The system is architected as a set of decoupled microservices that communicate through a central message broker, ensuring scalability and resilience.

```mermaid
graph TD
    A[Log Sources <br> /var/log, journalctl] --> B(Monitor Agent <br> monitor.py);
    B --> C{RabbitMQ <br> Message Queue};
    C --> D[Worker <br> worker.py];
    D -- Stores Sessions --> E(Redis);
    D -- Reads Sessions --> E;
    D -- Writes Verdicts --> F(PostgreSQL Database);
    
    G[FastAPI Backend <br> app/main.py] -- Reads Data --> F;
    G -- Manages Auth --> F;
    
    H[User's Browser <br> Frontend] <-->|HTTP API / WebSockets| G;
    
    I[Human Analyst] --> H;
    I -- Reviews Logs --> H;
    H -- Sends Feedback --> G;
    
    J[Retraining Script <br> update.py] -- Reads Reviewed Logs --> F;
    J -- Saves New Models --> K[Model Storage];
    D -- Loads Models --> K;

    subgraph "Real-time Ingestion"
        A
        B
        C
    end
    
    subgraph "AI Processing Core"
        D
        E
        K
    end
    
    subgraph "Data & Application Layer"
        F
        G
        H
    end
    
    subgraph "MLOps Feedback Loop"
        I
        J
    end



🧠 Key Concepts & Algorithms
This project utilizes several key machine learning concepts to achieve its high detection accuracy:

Log Parsing (Drain3): Unstructured log lines are parsed into structured templates (e.g., Failed password for * from *), allowing the system to understand the event type.

Vectorization (Sentence Transformers): Log messages are converted into high-dimensional numerical vectors (embeddings). This allows the ML models to understand the semantic meaning of logs, so Failed login and Authentication failure are treated as similar events.

Unsupervised Anomaly Detection (Autoencoder): An autoencoder neural network is trained only on normal logs. It learns to reconstruct normal data with very low error. When it sees an anomalous log, it fails to reconstruct it properly, resulting in a high "reconstruction error," which flags the log as a novel anomaly.

Sequential Analysis (LSTM Network): A Long Short-Term Memory (LSTM) network analyzes sequences of logs for a given user or IP. This allows it to detect complex, multi-step attacks (e.g., a port scan, followed by a failed login, followed by a successful login) that would appear normal as individual events.

Explainable AI (LIME): To build trust and aid investigation, the system uses LIME (Local Interpretable Model-agnostic Explanations) to highlight which words in a log message most contributed to it being flagged as an anomaly.


⚙️ Setup & Installation

Prerequisites-

Python 3.10+ & pip
PostgreSQL: A running instance with a database created.
RabbitMQ: A running instance.
Redis: A running instance.
Git for cloning the repository.

Installation Steps-

1. Clone the repository:

git clone <your-repo-url>
cd <your-repo-directory>

2. Create and activate a Python virtual environment:

python -m venv venv
source venv/bin/activate
# For Windows: venv\Scripts\activate

3. Install Python dependencies:

pip install -r requirements.txt

4. Install Playwright browser dependencies:

playwright install
# If on Linux, you may need to install system dependencies.
# See the Playwright docs or run the command for a list of missing libs.

5. Create the .env file:
Create a file named .env in the root directory. Copy the contents of .env.example (you should create this file) into it and fill in your details.

.env.example Template:

SECRET_KEY="<generate_a_long_random_32-byte_hex_key>"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

RABBITMQ_HOST="localhost"
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0

DATABASE_URL="postgresql://your_db_user:your_db_password@localhost:5432/your_db_name"

DASHBOARD_URL="[http://127.0.0.1:8000](http://127.0.0.1:8000)"
LOG_FILES_STR="/var/log/auth.log, /var/log/syslog" # Comma-separated
SESSION_TIMEOUT_SECONDS=1800
SEQUENCE_LEN=20
SIMILARITY_THRESHOLD=0.7

6. Set up the GeoIP Database:

Download the free GeoLite2 City database from MaxMind.
Create a geoip/ directory in the project root.
Place the GeoLite2-City.mmdb file inside the geoip/ directory.

7. Initialize the Database:

Ensure your PostgreSQL server is running and you have created the database specified in your DATABASE_URL.
Restore the database schema and any initial data (like a default user) using the provided dump_postgres.sql file:

psql -U your_db_user -d your_db_name -f dump_postgres.sql



▶️ How to Run

1. Start the services:

Ensure the run.sh script is executable: chmod +x run.sh
The script uses honcho, a process manager, and requires sudo to monitor system log files.

sudo ./run.sh

2. Access the Dashboard:

Navigate to http://127.0.0.1:8000 in your web browser. Log in with the default credentials.

3. Generate Test Data (Optional):

To see the system detect threats in real-time, run the powerful attack simulator in a separate terminal:

# Make sure your virtual environment is activated
python scripts/att_sim.py



🗺️ Roadmap & Future Work

This project is a strong foundation with many exciting avenues for future development:

-[ ] Full SOAR Integration: Develop a playbook engine to trigger automated responses (e.g., block IP via firewall API, disable user in Active Directory).

-[ ] Generative AI Assistant: Integrate an LLM for natural language querying of logs and automated incident report generation.

-[ ] Graph-Based Analysis: Model log data in a graph database (like Neo4j) to uncover complex relationships and lateral movement patterns.

-[ ] Threat Intelligence Feeds: Automatically enrich logs with data from threat feeds like AbuseIPDB and AlienVault OTX.

-[ ] MITRE ATT&CK Mapping: Tag all alerts with their corresponding MITRE ATT&CK tactics and techniques.



📜 License

This project is licensed under the MIT License - see the LICENSE.md file for details.