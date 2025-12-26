"""
Scanner module for executing security scanning tools.
Handles ModelScan, Picklescan, and AIsbom execution via subprocess.
"""
import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from .models import Finding, ToolResult
from .utils import logger


def get_tool_version(tool_name: str) -> str:
    """Get version of a tool."""
    try:
        if tool_name == "modelscan":
            result = subprocess.run(
                ["modelscan", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Parse version from output
            match = re.search(r'(\d+\.\d+\.\d+)', result.stdout + result.stderr)
            return match.group(1) if match else "unknown"
        elif tool_name == "picklescan":
            result = subprocess.run(
                ["picklescan", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Picklescan doesn't have --version, use package version
            try:
                import picklescan
                return getattr(picklescan, '__version__', 'unknown')
            except:
                return "unknown"
        elif tool_name == "aisbom":
            result = subprocess.run(
                ["aisbom", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            match = re.search(r'(\d+\.\d+\.\d+)', result.stdout + result.stderr)
            return match.group(1) if match else "unknown"
    except Exception as e:
        logger.error(f"Failed to get version for {tool_name}: {e}")
    return "unknown"


def run_modelscan(file_path: Path, output_path: Path) -> ToolResult:
    """
    Run ModelScan on a file.
    
    Args:
        file_path: Path to the model file
        output_path: Path to save JSON results
        
    Returns:
        ToolResult with scan findings
    """
    logger.info(f"Running ModelScan on {file_path}")
    
    version = get_tool_version("modelscan")
    findings: List[Finding] = []
    
    try:
        # Run modelscan with JSON output
        result = subprocess.run(
            [
                "modelscan",
                "-p", str(file_path),
                "-r", "json",
                "-o", str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        exit_code = result.returncode
        logger.info(f"ModelScan exit code: {exit_code}")
        
        # Parse the output JSON
        raw_output = None
        if output_path.exists():
            try:
                with open(output_path, 'r') as f:
                    raw_output = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Failed to parse ModelScan JSON output")
        
        # Extract findings from the result
        if raw_output:
            issues = raw_output.get("issues", [])
            for issue in issues:
                finding = Finding(
                    tool="modelscan",
                    severity=issue.get("severity", "UNKNOWN").upper(),
                    message=issue.get("description", issue.get("message", "Unknown issue")),
                    details={
                        "operator": issue.get("operator"),
                        "source": issue.get("source"),
                        "scanner": issue.get("scanner")
                    }
                )
                findings.append(finding)
        
        # Also check stderr for any issues
        if result.stderr and "error" in result.stderr.lower():
            logger.warning(f"ModelScan stderr: {result.stderr}")
        
        return ToolResult(
            tool="modelscan",
            version=version,
            exit_code=exit_code,
            findings_count=len(findings),
            findings=findings,
            raw_output=raw_output,
            error=result.stderr if exit_code == 2 else None
        )
        
    except subprocess.TimeoutExpired:
        logger.error("ModelScan timed out")
        return ToolResult(
            tool="modelscan",
            version=version,
            exit_code=-1,
            findings_count=0,
            findings=[],
            error="Scan timed out after 10 minutes"
        )
    except Exception as e:
        logger.error(f"ModelScan failed: {e}")
        return ToolResult(
            tool="modelscan",
            version=version,
            exit_code=-1,
            findings_count=0,
            findings=[],
            error=str(e)
        )


def run_picklescan(file_path: Path, output_path: Path) -> ToolResult:
    """
    Run Picklescan on a file.
    
    Args:
        file_path: Path to the model file
        output_path: Path to save JSON results
        
    Returns:
        ToolResult with scan findings
    """
    logger.info(f"Running Picklescan on {file_path}")
    
    version = get_tool_version("picklescan")
    findings: List[Finding] = []
    
    try:
        # Run picklescan
        result = subprocess.run(
            ["picklescan", "--path", str(file_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        exit_code = result.returncode
        logger.info(f"Picklescan exit code: {exit_code}")
        
        # Parse the text output
        raw_output = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": exit_code
        }
        
        # Extract dangerous globals from output
        # Format: "Dangerous global 'xxx' in module 'yyy'"
        dangerous_pattern = re.compile(r"dangerous.*?'([^']+)'.*?module\s*'([^']+)'", re.IGNORECASE)
        for match in dangerous_pattern.finditer(result.stdout):
            finding = Finding(
                tool="picklescan",
                severity="HIGH",
                message=f"Dangerous global '{match.group(1)}' found in module '{match.group(2)}'",
                details={"global": match.group(1), "module": match.group(2)}
            )
            findings.append(finding)
        
        # Check for infection in output
        if "infected" in result.stdout.lower() and exit_code == 1:
            if not findings:
                findings.append(Finding(
                    tool="picklescan",
                    severity="CRITICAL",
                    message="Picklescan detected malware/infection",
                    details={"raw_output": result.stdout}
                ))
        
        # Save results
        with open(output_path, 'w') as f:
            json.dump({
                "exit_code": exit_code,
                "findings": [f.model_dump() for f in findings],
                "raw_output": result.stdout
            }, f, indent=2)
        
        return ToolResult(
            tool="picklescan",
            version=version,
            exit_code=exit_code,
            findings_count=len(findings),
            findings=findings,
            raw_output=raw_output,
            error=result.stderr if exit_code == 2 else None
        )
        
    except subprocess.TimeoutExpired:
        logger.error("Picklescan timed out")
        return ToolResult(
            tool="picklescan",
            version=version,
            exit_code=-1,
            findings_count=0,
            findings=[],
            error="Scan timed out after 5 minutes"
        )
    except Exception as e:
        logger.error(f"Picklescan failed: {e}")
        return ToolResult(
            tool="picklescan",
            version=version,
            exit_code=-1,
            findings_count=0,
            findings=[],
            error=str(e)
        )


def generate_ai_sbom(file_path: Path, output_path: Path, file_hash: str = None) -> ToolResult:
    """
    Generate AI-SBOM (Software Bill of Materials) for a model file.
    Creates a CycloneDX v1.6 compatible SBOM with model metadata.
    
    Args:
        file_path: Path to the model file
        output_path: Path to save JSON results
        file_hash: Pre-computed SHA256 hash (optional)
        
    Returns:
        ToolResult with SBOM data
    """
    logger.info(f"Generating AI-SBOM for {file_path}")
    
    from datetime import datetime, timezone
    import uuid
    import hashlib
    
    version = "1.0.0"  # Internal SBOM generator version
    findings: List[Finding] = []
    
    try:
        # Calculate hash if not provided
        if not file_hash:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
            file_hash = sha256_hash.hexdigest()
        
        # Get file metadata
        file_stat = file_path.stat()
        file_ext = file_path.suffix.lower()
        
        # Determine model type from extension
        model_type_map = {
            ".pt": "pytorch",
            ".pth": "pytorch", 
            ".bin": "pytorch",
            ".pkl": "pickle",
            ".pickle": "pickle",
            ".joblib": "scikit-learn",
            ".h5": "keras",
            ".hdf5": "keras",
            ".keras": "keras",
            ".onnx": "onnx",
            ".pb": "tensorflow",
            ".tflite": "tensorflow-lite",
            ".safetensors": "safetensors",
            ".gguf": "gguf",
            ".mlmodel": "coreml"
        }
        
        model_type = model_type_map.get(file_ext, "unknown")
        
        # Try to extract metadata from model file
        model_metadata = _extract_model_metadata(file_path, file_ext)
        
        # Build CycloneDX v1.6 SBOM
        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tools": {
                    "components": [
                        {
                            "type": "application",
                            "name": "ai-model-scanner",
                            "version": version,
                            "description": "AI Model Security Scanner SBOM Generator"
                        }
                    ]
                },
                "component": {
                    "type": "machine-learning-model",
                    "name": file_path.stem,
                    "version": "1.0.0",
                    "description": f"AI/ML model file ({model_type})",
                    "hashes": [
                        {
                            "alg": "SHA-256",
                            "content": file_hash
                        }
                    ],
                    "properties": [
                        {"name": "model:format", "value": model_type},
                        {"name": "model:file_extension", "value": file_ext},
                        {"name": "model:file_size", "value": str(file_stat.st_size)},
                        {"name": "model:created", "value": datetime.fromtimestamp(file_stat.st_ctime, timezone.utc).isoformat()},
                        {"name": "model:modified", "value": datetime.fromtimestamp(file_stat.st_mtime, timezone.utc).isoformat()}
                    ]
                }
            },
            "components": [],
            "dependencies": [],
            "vulnerabilities": []
        }
        
        # Add extracted metadata as properties
        if model_metadata:
            for key, value in model_metadata.items():
                sbom["metadata"]["component"]["properties"].append({
                    "name": f"model:{key}",
                    "value": str(value) if not isinstance(value, str) else value
                })
            
            # Add framework as a component if detected
            if "framework" in model_metadata:
                sbom["components"].append({
                    "type": "framework",
                    "name": model_metadata["framework"],
                    "version": model_metadata.get("framework_version", "unknown"),
                    "bom-ref": f"framework-{model_metadata['framework']}"
                })
        
        # Check for license information
        if model_metadata and "license" in model_metadata:
            license_info = model_metadata["license"]
            if _is_restrictive_license(license_info):
                findings.append(Finding(
                    tool="aisbom",
                    severity="MEDIUM",
                    message=f"Restrictive license detected: {license_info}",
                    details={"license": license_info}
                ))
        
        # Save SBOM
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sbom, f, indent=2)
        
        return ToolResult(
            tool="aisbom",
            version=version,
            exit_code=0,
            findings_count=len(findings),
            findings=findings,
            raw_output=sbom,
            error=None
        )
        
    except Exception as e:
        logger.error(f"SBOM generation failed: {e}")
        return ToolResult(
            tool="aisbom",
            version=version,
            exit_code=-1,
            findings_count=0,
            findings=[],
            error=str(e)
        )


def _extract_model_metadata(file_path: Path, file_ext: str) -> Dict[str, Any]:
    """
    Extract metadata from model file without fully loading it.
    
    Args:
        file_path: Path to model file
        file_ext: File extension
        
    Returns:
        Dictionary of extracted metadata
    """
    metadata = {}
    
    try:
        if file_ext in [".safetensors"]:
            # Safetensors has JSON header at the start
            with open(file_path, "rb") as f:
                # First 8 bytes are header length
                header_size = int.from_bytes(f.read(8), "little")
                if header_size < 100 * 1024 * 1024:  # Sanity check: < 100MB header
                    header_bytes = f.read(header_size)
                    try:
                        header = json.loads(header_bytes.decode("utf-8"))
                        if "__metadata__" in header:
                            meta = header["__metadata__"]
                            metadata["format"] = meta.get("format", "safetensors")
                            if "license" in meta:
                                metadata["license"] = meta["license"]
                        
                        # Count tensors
                        tensor_count = len([k for k in header.keys() if not k.startswith("__")])
                        metadata["tensor_count"] = tensor_count
                        metadata["framework"] = "safetensors"
                    except json.JSONDecodeError:
                        pass
        
        elif file_ext in [".gguf"]:
            # GGUF has structured header
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic == b"GGUF":
                    metadata["format"] = "gguf"
                    metadata["framework"] = "llama.cpp"
                    # Version is next 4 bytes
                    version = int.from_bytes(f.read(4), "little")
                    metadata["gguf_version"] = version
        
        elif file_ext in [".pt", ".pth", ".bin"]:
            metadata["framework"] = "pytorch"
            metadata["serialization"] = "pickle-based"
        
        elif file_ext in [".h5", ".hdf5", ".keras"]:
            metadata["framework"] = "keras"
        
        elif file_ext in [".onnx"]:
            metadata["framework"] = "onnx"
        
        elif file_ext in [".pkl", ".pickle", ".joblib"]:
            metadata["serialization"] = "pickle"
            
    except Exception as e:
        logger.warning(f"Failed to extract metadata from {file_path}: {e}")
    
    return metadata


def _is_restrictive_license(license_str: str) -> bool:
    """Check if a license is restrictive for commercial use."""
    restrictive_patterns = [
        "non-commercial", "nc", "cc-by-nc", "research-only",
        "academic", "gpl", "agpl", "personal"
    ]
    license_lower = license_str.lower()
    return any(pattern in license_lower for pattern in restrictive_patterns)


def evaluate_policy(results: List[ToolResult], strict_policy: bool) -> Tuple[str, Optional[str]]:
    """
    Evaluate scan results against security policy.
    
    Args:
        results: List of tool results
        strict_policy: Whether to use strict policy
        
    Returns:
        Tuple of (pass_fail, fail_reason)
    """
    if not strict_policy:
        return "PASS", None
    
    fail_reasons = []
    
    for result in results:
        if result.tool in ["modelscan", "picklescan"]:
            # Check for high/critical findings
            for finding in result.findings:
                if finding.severity in ["HIGH", "CRITICAL"]:
                    fail_reasons.append(
                        f"{result.tool}: {finding.severity} - {finding.message}"
                    )
            
            # Check exit codes
            if result.tool == "modelscan" and result.exit_code == 1:
                if not any("modelscan" in r for r in fail_reasons):
                    fail_reasons.append("ModelScan found vulnerabilities")
            
            if result.tool == "picklescan" and result.exit_code == 1:
                if not any("picklescan" in r for r in fail_reasons):
                    fail_reasons.append("Picklescan detected malware")
    
    if fail_reasons:
        return "FAIL", "; ".join(fail_reasons[:5])  # Limit to 5 reasons
    
    return "PASS", None
