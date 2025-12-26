"""
Configuration settings for the AI Model Security Scanner.
All settings can be overridden via environment variables.
"""
import os
from pathlib import Path


class Config:
    """Application configuration."""
    
    # Data directories
    DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
    UPLOADS_DIR = DATA_DIR / "uploads"
    RESULTS_DIR = DATA_DIR / "results"
    LOGS_DIR = DATA_DIR / "logs"
    
    # Upload limits
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 5 * 1024 * 1024 * 1024))  # 5GB
    
    # Policy defaults
    STRICT_POLICY_DEFAULT = os.getenv("STRICT_POLICY_DEFAULT", "true").lower() == "true"
    ENABLE_PICKLESCAN_DEFAULT = os.getenv("ENABLE_PICKLESCAN_DEFAULT", "true").lower() == "true"
    RUN_AISBOM_ON_FAIL = os.getenv("RUN_AISBOM_ON_FAIL", "true").lower() == "true"
    
    # Job settings
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 2))
    JOB_RETENTION_DAYS = int(os.getenv("JOB_RETENTION_DAYS", 30))
    
    # Logging
    LOG_FILE = LOGS_DIR / "app.log"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8080))
    
    # Pickle-related extensions (for automatic picklescan trigger)
    PICKLE_EXTENSIONS = {".pkl", ".pickle", ".pt", ".pth", ".bin", ".joblib"}
    
    # All supported model extensions
    SUPPORTED_EXTENSIONS = {
        ".pkl", ".pickle", ".pt", ".pth", ".bin", ".joblib",
        ".h5", ".hdf5", ".keras", ".onnx", ".safetensors",
        ".gguf", ".pb", ".tflite", ".mlmodel"
    }
    
    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist."""
        cls.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        cls.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
