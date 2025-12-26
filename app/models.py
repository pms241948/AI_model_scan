"""
Pydantic models for request/response validation.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutputFormat(str, Enum):
    """Output format options."""
    JSON = "json"
    ZIP = "zip"


class JobOptions(BaseModel):
    """Options for job creation."""
    enable_picklescan: bool = True
    strict_policy: bool = True
    output_format: OutputFormat = OutputFormat.JSON
    run_aisbom_on_fail: bool = True


class Finding(BaseModel):
    """A single security finding."""
    tool: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ToolResult(BaseModel):
    """Result from a single tool execution."""
    tool: str
    version: str
    exit_code: int
    findings_count: int
    findings: List[Finding] = []
    raw_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScanSummary(BaseModel):
    """Summary of all scan results."""
    job_id: str
    filename: str
    file_extension: str
    sha256: str
    file_size: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: JobStatus
    pass_fail: Optional[str] = None  # "PASS" or "FAIL"
    fail_reason: Optional[str] = None
    tools_run: List[str] = []
    tool_versions: Dict[str, str] = {}
    total_findings: int = 0
    findings_by_severity: Dict[str, int] = {}
    findings_by_tool: Dict[str, int] = {}
    top_findings: List[Finding] = []
    options: JobOptions = JobOptions()


class JobCreateResponse(BaseModel):
    """Response after creating a job."""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    job_id: str
    status: JobStatus
    summary: Optional[ScanSummary] = None
    error: Optional[str] = None


class ArtifactInfo(BaseModel):
    """Information about an artifact file."""
    name: str
    size: int
    content_type: str


class ArtifactsResponse(BaseModel):
    """Response listing all artifacts."""
    job_id: str
    artifacts: List[ArtifactInfo]


class JobListItem(BaseModel):
    """Item in job list."""
    job_id: str
    filename: str
    status: JobStatus
    created_at: datetime
    pass_fail: Optional[str] = None


class JobListResponse(BaseModel):
    """Response listing all jobs."""
    jobs: List[JobListItem]
    total: int
