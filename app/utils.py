"""
Utility functions for file handling, hashing, and other common operations.
"""
import hashlib
import json
import zipfile
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import config

# Configure logging
def setup_logging():
    """Set up application logging."""
    config.ensure_directories()
    
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("ai_model_scanner")

logger = setup_logging()


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return Path(filename).suffix.lower()


def is_pickle_format(filename: str) -> bool:
    """Check if file is a pickle-based format."""
    ext = get_file_extension(filename)
    return ext in config.PICKLE_EXTENSIONS


def is_supported_format(filename: str) -> bool:
    """Check if file format is supported."""
    ext = get_file_extension(filename)
    return ext in config.SUPPORTED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal.
    Returns a safe internal filename.
    """
    # Remove any path components
    name = Path(filename).name
    # Remove any potentially dangerous characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    sanitized = "".join(c if c in safe_chars else "_" for c in name)
    return sanitized if sanitized else "model_file"


def save_json(data: dict, file_path: Path) -> None:
    """Save data as JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(file_path: Path) -> Optional[dict]:
    """Load JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def create_artifacts_zip(job_dir: Path, output_path: Path) -> None:
    """Create a ZIP archive of all job artifacts."""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in job_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".json":
                zf.write(file_path, file_path.name)


def get_content_type(filename: str) -> str:
    """Get content type for a file."""
    ext = get_file_extension(filename)
    content_types = {
        ".json": "application/json",
        ".zip": "application/zip",
        ".txt": "text/plain",
    }
    return content_types.get(ext, "application/octet-stream")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def cleanup_old_jobs(days: int = None) -> int:
    """
    Clean up jobs older than specified days.
    Returns number of jobs deleted.
    """
    if days is None:
        days = config.JOB_RETENTION_DAYS
    
    deleted = 0
    cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
    
    # Clean uploads
    for job_dir in config.UPLOADS_DIR.iterdir():
        if job_dir.is_dir():
            try:
                mtime = job_dir.stat().st_mtime
                if mtime < cutoff:
                    import shutil
                    shutil.rmtree(job_dir)
                    deleted += 1
            except Exception as e:
                logger.error(f"Error cleaning up {job_dir}: {e}")
    
    # Clean results
    for job_dir in config.RESULTS_DIR.iterdir():
        if job_dir.is_dir():
            try:
                mtime = job_dir.stat().st_mtime
                if mtime < cutoff:
                    import shutil
                    shutil.rmtree(job_dir)
            except Exception as e:
                logger.error(f"Error cleaning up {job_dir}: {e}")
    
    return deleted
