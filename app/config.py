# app/config.py
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    
    # Elasticsearch settings
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ES_ENABLED: bool = False
    ES_INDEX_LOGS: str = "logs"
    ES_INDEX_ALERTS: str = "alerts"

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
    SLACK_WEBHOOK_URL: Optional[str] = None
    LOG_SHIPPER_API_KEY: Optional[str] = "dev_secret_key"  # Default for dev, should be in .env
    ENVIRONMENT: str = "development"  # "development" or "production"
    
    # LLM Multi-Provider Configuration
    LLM_DEFAULT_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None
    OLLAMA_HOST: str = "http://localhost:11434"
    LLM_CACHE_TTL: int = 3600  # 1 hour default cache
    
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

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
        # Load from model_registry.json to always use the latest compatible model
        import json
        registry_path = self.PROJECT_ROOT / "model_registry.json"
        if registry_path.exists():
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            return self.PROJECT_ROOT / registry.get("supervised_model", "model/sgd_embedder.pkl")
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

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding='utf-8', extra='ignore')

# Create a single instance of the settings to be used by the whole app
settings = Settings()
