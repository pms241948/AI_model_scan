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


def is_upload_supported(filename: str) -> bool:
    """Check if file format is supported for upload (includes archives)."""
    ext = get_file_extension(filename)
    # Handle double extensions like .tar.gz
    if filename.lower().endswith('.tar.gz'):
        return True
    return ext in config.UPLOAD_EXTENSIONS


def is_archive_file(filename: str) -> bool:
    """Check if file is an archive (ZIP, tar, tar.gz, tgz)."""
    lower = filename.lower()
    if lower.endswith('.tar.gz') or lower.endswith('.tgz'):
        return True
    ext = get_file_extension(filename)
    return ext in {".zip", ".tar", ".gz"}


def get_archive_type(filename: str) -> str:
    """Get archive type from filename."""
    lower = filename.lower()
    if lower.endswith('.tar.gz') or lower.endswith('.tgz'):
        return "tar.gz"
    elif lower.endswith('.tar'):
        return "tar"
    elif lower.endswith('.zip'):
        return "zip"
    elif lower.endswith('.gz'):
        return "gz"
    return "unknown"


def extract_zip_models(zip_path: Path, extract_dir: Path) -> list[Path]:
    """
    Extract ZIP archive and return list of model files found.
    
    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to
        
    Returns:
        List of paths to model files
    """
    model_files = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Security check: ensure no path traversal
            for member in zf.namelist():
                # Skip directories and hidden files
                if member.endswith('/') or member.startswith('.') or '/..' in member:
                    continue
                
                # Check for path traversal
                member_path = Path(member)
                if '..' in member_path.parts:
                    logger.warning(f"Skipping suspicious path in ZIP: {member}")
                    continue
                
                # Extract only model files
                ext = get_file_extension(member)
                if ext in config.SUPPORTED_EXTENSIONS:
                    # Extract to flat structure with unique names
                    safe_name = sanitize_filename(member_path.name)
                    target_path = extract_dir / safe_name
                    
                    # Handle duplicates
                    counter = 1
                    while target_path.exists():
                        stem = member_path.stem
                        target_path = extract_dir / f"{stem}_{counter}{ext}"
                        counter += 1
                    
                    # Extract file
                    with zf.open(member) as src, open(target_path, 'wb') as dst:
                        import shutil
                        shutil.copyfileobj(src, dst)
                    
                    model_files.append(target_path)
                    logger.info(f"Extracted model file: {target_path.name}")
        
        # Remove the original ZIP file
        zip_path.unlink()
        
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        raise ValueError(f"Invalid ZIP file: {e}")
    except Exception as e:
        logger.error(f"Failed to extract ZIP: {e}")
        raise
    
    return model_files


def extract_tar_models(tar_path: Path, extract_dir: Path) -> list[Path]:
    """
    Extract tar/tar.gz archive and return list of model files found.
    
    Args:
        tar_path: Path to tar file
        extract_dir: Directory to extract to
        
    Returns:
        List of paths to model files
    """
    import tarfile
    
    model_files = []
    
    try:
        # Determine tar mode
        mode = 'r:gz' if tar_path.name.lower().endswith(('.tar.gz', '.tgz')) else 'r'
        
        with tarfile.open(tar_path, mode) as tf:
            for member in tf.getmembers():
                # Skip directories
                if member.isdir():
                    continue
                
                # Skip hidden files
                if member.name.startswith('.') or '/.' in member.name:
                    continue
                
                # Check for path traversal
                if '..' in member.name:
                    logger.warning(f"Skipping suspicious path in tar: {member.name}")
                    continue
                
                # Extract only model files
                ext = get_file_extension(member.name)
                if ext in config.SUPPORTED_EXTENSIONS:
                    member_path = Path(member.name)
                    safe_name = sanitize_filename(member_path.name)
                    target_path = extract_dir / safe_name
                    
                    # Handle duplicates
                    counter = 1
                    while target_path.exists():
                        stem = member_path.stem
                        target_path = extract_dir / f"{stem}_{counter}{ext}"
                        counter += 1
                    
                    # Extract file
                    member.name = target_path.name  # Rename to safe name
                    tf.extract(member, extract_dir)
                    
                    # Move to correct location if extracted to subdirectory
                    extracted_path = extract_dir / target_path.name
                    if extracted_path.exists():
                        model_files.append(extracted_path)
                        logger.info(f"Extracted model file: {extracted_path.name}")
        
        # Remove the original tar file
        tar_path.unlink()
        
    except tarfile.TarError as e:
        logger.error(f"Invalid tar file: {e}")
        raise ValueError(f"Invalid tar file: {e}")
    except Exception as e:
        logger.error(f"Failed to extract tar: {e}")
        raise
    
    return model_files


def extract_archive_models(archive_path: Path, extract_dir: Path, archive_type: str) -> list[Path]:
    """
    Extract models from an archive file.
    
    Args:
        archive_path: Path to archive file
        extract_dir: Directory to extract to
        archive_type: Type of archive (zip, tar, tar.gz)
        
    Returns:
        List of paths to model files
    """
    if archive_type == "zip":
        return extract_zip_models(archive_path, extract_dir)
    elif archive_type in ("tar", "tar.gz"):
        return extract_tar_models(archive_path, extract_dir)
    else:
        raise ValueError(f"Unsupported archive type: {archive_type}")


def list_mounted_models() -> list[dict]:
    """
    List model files in the mounted models directory.
    
    Returns:
        List of model info dicts with name, path, size, type, etc.
    """
    models = []
    
    if not config.MODELS_DIR.exists():
        logger.warning(f"Models directory does not exist: {config.MODELS_DIR}")
        return models
    
    def scan_directory(directory: Path, prefix: str = ""):
        """Recursively scan directory for model files."""
        try:
            for item in sorted(directory.iterdir()):
                relative_path = f"{prefix}/{item.name}" if prefix else item.name
                
                if item.is_file():
                    ext = get_file_extension(item.name)
                    if ext in config.SUPPORTED_EXTENSIONS:
                        stat = item.stat()
                        models.append({
                            "name": item.name,
                            "path": relative_path,
                            "full_path": str(item),
                            "size": stat.st_size,
                            "size_formatted": format_file_size(stat.st_size),
                            "extension": ext,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "is_pickle": ext in config.PICKLE_EXTENSIONS,
                            "type": "file"
                        })
                elif item.is_dir():
                    # Check if directory contains model files (is a model folder)
                    model_count = sum(
                        1 for f in item.rglob("*") 
                        if f.is_file() and get_file_extension(f.name) in config.SUPPORTED_EXTENSIONS
                    )
                    if model_count > 0:
                        # Get total size of directory
                        total_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        models.append({
                            "name": item.name,
                            "path": relative_path,
                            "full_path": str(item),
                            "size": total_size,
                            "size_formatted": format_file_size(total_size),
                            "extension": "folder",
                            "model_count": model_count,
                            "type": "folder"
                        })
        except PermissionError as e:
            logger.warning(f"Permission denied scanning {directory}: {e}")
    
    scan_directory(config.MODELS_DIR)
    return models


def get_model_files_in_path(model_path: str) -> list[Path]:
    """
    Get all model files in a given path (file or directory).
    
    Args:
        model_path: Relative path from MODELS_DIR
        
    Returns:
        List of absolute paths to model files
    """
    # Prevent path traversal
    if '..' in model_path:
        raise ValueError("Invalid path")
    
    full_path = config.MODELS_DIR / model_path
    
    if not full_path.exists():
        raise FileNotFoundError(f"Path not found: {model_path}")
    
    # Ensure path is within MODELS_DIR
    try:
        full_path.resolve().relative_to(config.MODELS_DIR.resolve())
    except ValueError:
        raise ValueError("Path traversal not allowed")
    
    model_files = []
    
    if full_path.is_file():
        ext = get_file_extension(full_path.name)
        if ext in config.SUPPORTED_EXTENSIONS:
            model_files.append(full_path)
    elif full_path.is_dir():
        for f in full_path.rglob("*"):
            if f.is_file():
                ext = get_file_extension(f.name)
                if ext in config.SUPPORTED_EXTENSIONS:
                    model_files.append(f)
    
    return model_files

