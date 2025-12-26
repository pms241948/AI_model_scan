"""
Job manager for handling scan jobs with concurrency control.
"""
import asyncio
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from collections import OrderedDict

from .config import config
from .models import (
    JobStatus, JobOptions, ScanSummary, JobListItem,
    Finding, ToolResult
)
from .utils import (
    logger, calculate_sha256, get_file_extension,
    is_pickle_format, save_json, load_json, create_artifacts_zip,
    extract_archive_models
)
from .scanner import run_modelscan, run_picklescan, generate_ai_sbom, evaluate_policy


class JobManager:
    """Manages scan jobs with concurrency control."""
    
    def __init__(self):
        self.jobs: Dict[str, ScanSummary] = OrderedDict()
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.active_jobs: int = 0
        self.lock = asyncio.Lock()
        self._workers_started = False
        
        # Load existing jobs from disk
        self._load_existing_jobs()
    
    def _load_existing_jobs(self):
        """Load existing job summaries from disk."""
        try:
            for job_dir in config.RESULTS_DIR.iterdir():
                if job_dir.is_dir():
                    summary_path = job_dir / "summary.json"
                    if summary_path.exists():
                        data = load_json(summary_path)
                        if data:
                            try:
                                summary = ScanSummary(**data)
                                self.jobs[summary.job_id] = summary
                            except Exception as e:
                                logger.warning(f"Failed to load job {job_dir.name}: {e}")
        except FileNotFoundError:
            pass
        
        logger.info(f"Loaded {len(self.jobs)} existing jobs")
    
    async def start_workers(self):
        """Start background worker tasks."""
        if self._workers_started:
            return
        
        self._workers_started = True
        for i in range(config.MAX_CONCURRENT_JOBS):
            asyncio.create_task(self._worker(i))
        logger.info(f"Started {config.MAX_CONCURRENT_JOBS} worker tasks")
    
    async def _worker(self, worker_id: int):
        """Background worker that processes jobs from the queue."""
        logger.info(f"Worker {worker_id} started")
        
        while True:
            try:
                job_id = await self.job_queue.get()
                logger.info(f"Worker {worker_id} processing job {job_id}")
                
                async with self.lock:
                    self.active_jobs += 1
                
                try:
                    await self._process_job(job_id)
                except Exception as e:
                    logger.error(f"Worker {worker_id} failed processing job {job_id}: {e}")
                    await self._fail_job(job_id, str(e))
                finally:
                    async with self.lock:
                        self.active_jobs -= 1
                    self.job_queue.task_done()
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
    
    async def create_job(
        self,
        file_path: Path,
        original_filename: str,
        options: JobOptions,
        archive_type: str = None
    ) -> str:
        """
        Create a new scan job.
        
        Args:
            file_path: Path to uploaded file
            original_filename: Original filename from upload
            options: Scan options
            archive_type: Archive type (zip, tar, tar.gz) or None for regular files
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        # Create job directories
        upload_dir = config.UPLOADS_DIR / job_id
        results_dir = config.RESULTS_DIR / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        model_files = []
        
        if archive_type:
            # Move archive to upload_dir first
            archive_ext = ".tar.gz" if archive_type == "tar.gz" else f".{archive_type}"
            archive_path = upload_dir / f"archive{archive_ext}"
            shutil.move(str(file_path), str(archive_path))
            
            # Extract model files from archive
            model_files = extract_archive_models(archive_path, upload_dir, archive_type)
            
            if not model_files:
                shutil.rmtree(upload_dir)
                shutil.rmtree(results_dir)
                raise ValueError(f"No model files found in {archive_type.upper()} archive")
            
            # Use first file for primary info, but scan all
            primary_file = model_files[0]
            original_filename = f"{original_filename} ({len(model_files)} files)"
        else:
            # Regular single file
            internal_filename = f"model{get_file_extension(original_filename)}"
            job_file_path = upload_dir / internal_filename
            shutil.move(str(file_path), str(job_file_path))
            model_files = [job_file_path]
            primary_file = job_file_path
        
        # Calculate file hash for primary/first file
        file_hash = calculate_sha256(primary_file)
        total_size = sum(f.stat().st_size for f in model_files)
        
        # Create initial summary
        summary = ScanSummary(
            job_id=job_id,
            filename=original_filename,
            file_extension=get_file_extension(primary_file.name),
            sha256=file_hash,
            file_size=total_size,
            started_at=datetime.now(),
            status=JobStatus.QUEUED,
            options=options
        )
        
        self.jobs[job_id] = summary
        save_json(summary.model_dump(), results_dir / "summary.json")
        
        # Queue the job
        await self.job_queue.put(job_id)
        logger.info(f"Created job {job_id} for {original_filename}")
        
        return job_id
    
    async def create_mounted_model_job(
        self,
        model_path: str,
        model_files: List[Path],
        options: JobOptions
    ) -> str:
        """
        Create a scan job for models in the mounted directory.
        
        Args:
            model_path: Relative path from /models directory
            model_files: List of absolute paths to model files
            options: Scan options
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        # Create job directories
        upload_dir = config.UPLOADS_DIR / job_id
        results_dir = config.RESULTS_DIR / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Create symlinks or copy files (use symlinks for efficiency)
        job_model_files = []
        for i, src_file in enumerate(model_files):
            # Create symlink in upload dir
            link_name = f"model_{i}{src_file.suffix}"
            link_path = upload_dir / link_name
            try:
                link_path.symlink_to(src_file)
            except OSError:
                # Symlink not supported, copy instead
                shutil.copy2(src_file, link_path)
            job_model_files.append(link_path)
        
        # Use first file for primary info
        primary_file = model_files[0]
        file_hash = calculate_sha256(primary_file)
        total_size = sum(f.stat().st_size for f in model_files)
        
        # Create initial summary
        display_name = model_path
        if len(model_files) > 1:
            display_name = f"{model_path} ({len(model_files)} files)"
        
        summary = ScanSummary(
            job_id=job_id,
            filename=display_name,
            file_extension=get_file_extension(primary_file.name),
            sha256=file_hash,
            file_size=total_size,
            started_at=datetime.now(),
            status=JobStatus.QUEUED,
            options=options
        )
        
        self.jobs[job_id] = summary
        save_json(summary.model_dump(), results_dir / "summary.json")
        
        # Queue the job
        await self.job_queue.put(job_id)
        logger.info(f"Created mounted model job {job_id} for {model_path}")
        
        return job_id
    
    async def _process_job(self, job_id: str):
        """Process a scan job."""
        summary = self.jobs.get(job_id)
        if not summary:
            logger.error(f"Job {job_id} not found")
            return
        
        # Update status to running
        summary.status = JobStatus.RUNNING
        self._save_summary(summary)
        
        upload_dir = config.UPLOADS_DIR / job_id
        results_dir = config.RESULTS_DIR / job_id
        
        # Find all model files (handles single files, ZIPs, and mounted models)
        model_files = [
            f for f in upload_dir.iterdir() 
            if f.is_file() or f.is_symlink()
        ]
        model_files = [
            f for f in model_files 
            if get_file_extension(f.name) in config.SUPPORTED_EXTENSIONS
        ]
        
        if not model_files:
            await self._fail_job(job_id, "No model files found")
            return
        
        results: List[ToolResult] = []
        total_modelscan_findings = 0
        total_picklescan_findings = 0
        
        # Scan each model file
        for i, model_file in enumerate(model_files):
            file_suffix = f"_{i}" if len(model_files) > 1 else ""
            
            # Run ModelScan
            modelscan_output = results_dir / f"modelscan{file_suffix}.json"
            modelscan_result = await asyncio.to_thread(
                run_modelscan, model_file, modelscan_output
            )
            results.append(modelscan_result)
            total_modelscan_findings += modelscan_result.findings_count
            
            if i == 0:
                summary.tools_run.append("modelscan")
                summary.tool_versions["modelscan"] = modelscan_result.version
            
            # Run Picklescan if enabled and file is pickle format
            if summary.options.enable_picklescan and is_pickle_format(model_file.name):
                picklescan_output = results_dir / f"picklescan{file_suffix}.json"
                picklescan_result = await asyncio.to_thread(
                    run_picklescan, model_file, picklescan_output
                )
                results.append(picklescan_result)
                total_picklescan_findings += picklescan_result.findings_count
                
                if "picklescan" not in summary.tools_run:
                    summary.tools_run.append("picklescan")
                    summary.tool_versions["picklescan"] = picklescan_result.version
        
        summary.findings_by_tool["modelscan"] = total_modelscan_findings
        if total_picklescan_findings > 0 or "picklescan" in summary.tools_run:
            summary.findings_by_tool["picklescan"] = total_picklescan_findings
        
        # Evaluate policy based on all results
        pass_fail, fail_reason = evaluate_policy(results, summary.options.strict_policy)
        summary.pass_fail = pass_fail
        summary.fail_reason = fail_reason
        
        # Run AIsbom on first file (if policy passes or run_aisbom_on_fail is True)
        if pass_fail == "PASS" or summary.options.run_aisbom_on_fail:
            primary_file = model_files[0]
            aisbom_output = results_dir / "aisbom.json"
            aisbom_result = await asyncio.to_thread(
                generate_ai_sbom, primary_file, aisbom_output, summary.sha256
            )
            results.append(aisbom_result)
            summary.tools_run.append("aisbom")
            summary.tool_versions["aisbom"] = aisbom_result.version
            summary.findings_by_tool["aisbom"] = aisbom_result.findings_count
        
        # Aggregate findings
        all_findings: List[Finding] = []
        severity_counts: Dict[str, int] = {}
        
        for result in results:
            all_findings.extend(result.findings)
            for finding in result.findings:
                severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        
        summary.total_findings = len(all_findings)
        summary.findings_by_severity = severity_counts
        summary.top_findings = all_findings[:20]  # Limit to top 20
        
        # Create artifacts ZIP
        zip_path = results_dir / "artifacts.zip"
        await asyncio.to_thread(create_artifacts_zip, results_dir, zip_path)
        
        # Finalize
        summary.finished_at = datetime.now()
        summary.status = JobStatus.SUCCEEDED if pass_fail == "PASS" else JobStatus.FAILED
        self._save_summary(summary)
        
        logger.info(f"Job {job_id} completed: {pass_fail}")
    
    async def _fail_job(self, job_id: str, error: str):
        """Mark a job as failed."""
        summary = self.jobs.get(job_id)
        if summary:
            summary.status = JobStatus.FAILED
            summary.finished_at = datetime.now()
            summary.fail_reason = error
            self._save_summary(summary)
        logger.error(f"Job {job_id} failed: {error}")
    
    def _save_summary(self, summary: ScanSummary):
        """Save job summary to disk."""
        results_dir = config.RESULTS_DIR / summary.job_id
        save_json(summary.model_dump(), results_dir / "summary.json")
        self.jobs[summary.job_id] = summary
    
    def get_job(self, job_id: str) -> Optional[ScanSummary]:
        """Get job summary by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, limit: int = 100) -> List[JobListItem]:
        """List all jobs, most recent first."""
        items = []
        for job_id, summary in reversed(list(self.jobs.items())):
            items.append(JobListItem(
                job_id=job_id,
                filename=summary.filename,
                status=summary.status,
                created_at=summary.started_at,
                pass_fail=summary.pass_fail
            ))
            if len(items) >= limit:
                break
        return items
    
    def get_artifacts(self, job_id: str) -> List[Path]:
        """Get list of artifact files for a job."""
        results_dir = config.RESULTS_DIR / job_id
        if not results_dir.exists():
            return []
        
        return [f for f in results_dir.iterdir() if f.is_file()]
    
    def get_artifact_path(self, job_id: str, artifact_name: str) -> Optional[Path]:
        """Get path to a specific artifact."""
        # Prevent path traversal
        if ".." in artifact_name or "/" in artifact_name:
            return None
        
        artifact_path = config.RESULTS_DIR / job_id / artifact_name
        if artifact_path.exists() and artifact_path.is_file():
            return artifact_path
        return None
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and its files."""
        if job_id not in self.jobs:
            return False
        
        # Remove directories
        upload_dir = config.UPLOADS_DIR / job_id
        results_dir = config.RESULTS_DIR / job_id
        
        try:
            if upload_dir.exists():
                shutil.rmtree(upload_dir)
            if results_dir.exists():
                shutil.rmtree(results_dir)
            del self.jobs[job_id]
            logger.info(f"Deleted job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False


# Global job manager instance
job_manager = JobManager()
