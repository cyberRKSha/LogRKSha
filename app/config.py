# app/config.py
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class Settings(BaseSettings):

    # Define the root directory of your project
    PROJECT_ROOT: Path = PROJECT_ROOT

    # Security settings, loaded from the .env file
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Infrastructure settings
    RABBITMQ_HOST: str
    DASHBOARD_URL: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    SESSION_TIMEOUT_SECONDS: int
    SEQUENCE_LEN: int
    
    # Base directory settings
    # DB_NAME: str
    DATABASE_URL: str
    LOG_FILES_STR: str
    SIMILARITY_THRESHOLD: float
    MODEL_DIR: Path = PROJECT_ROOT / "model"
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    DATA_DIR: Path = PROJECT_ROOT / "data"
    SIMULATION_DIR: Path = PROJECT_ROOT / "simulation"
    STATIC_PATH: Path = PROJECT_ROOT / "app" / "static"
    TEMPLATES_PATH: Path = PROJECT_ROOT / "app" / "templates"
    GEOIP_PATH: Path = PROJECT_ROOT / "geoip" / "GeoLite2-City.mmdb"
    ABUSEIPDB_API_KEY: Optional[str] = None

    # --- Automatically constructed paths ---
    # This creates the full paths to your files from the settings above
    
    # @property
    # def DATABASE_FILE(self) -> Path:
    #     return self.PROJECT_ROOT / self.DB_NAME

    @property
    def LOG_FILES(self) -> list[str]:
        paths = [p.strip() for p in self.LOG_FILES_STR.split(',')]
        full_paths = []
        for path in paths:
            if os.path.isabs(path):
                full_paths.append(path)
            else:
                full_paths.append(str(self.PROJECT_ROOT / path))
        return full_paths

    @property
    def CHECKPOINT_FILE(self) -> Path:
        return self.MODEL_DIR / "last_processed_log_id.txt"
    
    @property
    def DRAIN_MODEL_PATH(self) -> Path:
        return self.MODEL_DIR / "drain_miner.pkl"

    @property
    def EMBEDDER_PATH(self) -> str:
        return str(self.MODEL_DIR / "sentence_transformer_model")

    @property
    def SUPERVISED_MODEL_PATH(self) -> Path:
        return self.MODEL_DIR / "sgd_embedder.pkl"

    @property
    def AUTOENCODER_PATH(self) -> Path:
        return self.MODEL_DIR / "autoencoder_model.keras"

    @property
    def THRESHOLD_PATH(self) -> Path:
        return self.MODEL_DIR / "autoencoder_threshold.json"

    @property
    def EXPLAINER_PATH(self) -> Path:
        return self.MODEL_DIR / "lime_explainer.pkl"
    
    @property
    def LSTM_MODEL_PATH(self) -> Path:
        return self.MODEL_DIR / "lstm_classifier_model.keras"

    @property
    def KNOWN_HASHES_FILE(self) -> Path:
        return self.LOG_DIR / "kwnhashes.txt"

    @property
    def ALERT_SOUND(self) -> Path:
        return self.LOG_DIR / "alert.wav"

    @property
    def STATUS_FILE(self) -> Path:
        return self.PROJECT_ROOT / "monitoring_status.json"

    model_config = ConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra='ignore')

# Create a single instance of the settings to be used by the whole app
settings = Settings()
