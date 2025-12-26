"""
FastAPI application for AI Model Security Scanner.
Provides REST API and web UI for model scanning and SBOM generation.
"""
import os
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import config
from .models import (
    JobStatus, JobOptions, OutputFormat,
    JobCreateResponse, JobStatusResponse, ArtifactsResponse, 
    ArtifactInfo, JobListResponse
)
from .job_manager import job_manager
from .utils import (
    logger, sanitize_filename, is_supported_format, 
    get_content_type, format_file_size
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    config.ensure_directories()
    await job_manager.start_workers()
    logger.info("AI Model Security Scanner started")
    
    yield
    
    # Shutdown
    logger.info("AI Model Security Scanner shutting down")


app = FastAPI(
    title="AI Model Security Scanner",
    description="Security scanning and SBOM generation for AI/ML models",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

# Add custom template filters
templates.env.filters["format_size"] = format_file_size


# ============== Health Check ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ai-model-scanner"}


# ============== REST API Endpoints ==============

@app.post("/api/jobs", response_model=JobCreateResponse)
async def create_job(
    file: UploadFile = File(...),
    enable_picklescan: bool = Form(True),
    strict_policy: bool = Form(True),
    output_format: str = Form("json"),
    run_aisbom_on_fail: bool = Form(True)
):
    """
    Create a new scan job.
    
    Upload a model file and start security scanning.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file extension
    if not is_supported_format(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Supported: {', '.join(config.SUPPORTED_EXTENSIONS)}"
        )
    
    # Check file size (read in chunks to avoid memory issues)
    temp_path = None
    try:
        # Create temp file in data directory
        config.ensure_directories()
        temp_fd, temp_path = tempfile.mkstemp(dir=str(config.DATA_DIR))
        
        total_size = 0
        with os.fdopen(temp_fd, 'wb') as temp_file:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > config.MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {format_file_size(config.MAX_UPLOAD_SIZE)}"
                    )
                temp_file.write(chunk)
        
        # Create job options
        options = JobOptions(
            enable_picklescan=enable_picklescan,
            strict_policy=strict_policy,
            output_format=OutputFormat(output_format.lower()),
            run_aisbom_on_fail=run_aisbom_on_fail
        )
        
        # Sanitize filename and create job
        safe_filename = sanitize_filename(file.filename)
        job_id = await job_manager.create_job(
            file_path=Path(temp_path),
            original_filename=safe_filename,
            options=options
        )
        
        temp_path = None  # Ownership transferred to job manager
        
        return JobCreateResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            message="Job created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file if not transferred
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@app.get("/api/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 100):
    """List all jobs."""
    jobs = job_manager.list_jobs(limit=limit)
    return JobListResponse(jobs=jobs, total=len(jobs))


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status and summary."""
    summary = job_manager.get_job(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job_id,
        status=summary.status,
        summary=summary,
        error=summary.fail_reason
    )


@app.get("/api/jobs/{job_id}/artifacts", response_model=ArtifactsResponse)
async def get_artifacts(job_id: str):
    """List job artifacts."""
    summary = job_manager.get_job(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    
    artifacts = []
    for artifact_path in job_manager.get_artifacts(job_id):
        artifacts.append(ArtifactInfo(
            name=artifact_path.name,
            size=artifact_path.stat().st_size,
            content_type=get_content_type(artifact_path.name)
        ))
    
    return ArtifactsResponse(job_id=job_id, artifacts=artifacts)


@app.get("/api/jobs/{job_id}/download/{artifact_name}")
async def download_artifact(job_id: str, artifact_name: str):
    """Download a specific artifact."""
    summary = job_manager.get_job(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    
    artifact_path = job_manager.get_artifact_path(job_id, artifact_name)
    if not artifact_path:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return FileResponse(
        path=artifact_path,
        filename=artifact_name,
        media_type=get_content_type(artifact_name)
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its artifacts."""
    if await job_manager.delete_job(job_id):
        return {"status": "deleted", "job_id": job_id}
    raise HTTPException(status_code=404, detail="Job not found")


# ============== Web UI Routes ==============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page with upload form."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "max_upload_size": format_file_size(config.MAX_UPLOAD_SIZE),
        "supported_extensions": list(config.SUPPORTED_EXTENSIONS)
    })


@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Jobs list page."""
    jobs = job_manager.list_jobs()
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "jobs": jobs
    })


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_result_page(request: Request, job_id: str):
    """Job result page."""
    summary = job_manager.get_job(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    
    artifacts = job_manager.get_artifacts(job_id)
    artifact_infos = [
        {
            "name": a.name,
            "size": format_file_size(a.stat().st_size),
            "content_type": get_content_type(a.name)
        }
        for a in artifacts
    ]
    
    return templates.TemplateResponse("result.html", {
        "request": request,
        "job": summary,
        "artifacts": artifact_infos
    })


# ============== Error Handlers ==============

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error_code": 404,
        "error_message": "Page not found"
    }, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    """Handle 500 errors."""
    logger.error(f"Server error: {exc}")
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error_code": 500,
        "error_message": "Internal server error"
    }, status_code=500)
