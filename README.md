# AI Model Security Scanner

A fully air-gapped web application for **AI/ML model security scanning** and **AI-SBOM generation**.

## Features

- 🛡️ **Vulnerability Scanning**: Security checks using ModelScan and Picklescan
- 📋 **AI-SBOM Generation**: Automatic CycloneDX v1.6 SBOM creation
- 🌐 **Web UI**: Intuitive file upload and result viewing interface
- 🔌 **REST API**: API endpoints for automation
- 🔒 **Fully Offline**: 100% operational without network connectivity

## Supported Model Formats

| Format | Extensions | Picklescan Support |
|--------|------------|-------------------|
| PyTorch | `.pt`, `.pth`, `.bin` | ✅ |
| Pickle | `.pkl`, `.pickle`, `.joblib` | ✅ |
| Keras/TF | `.h5`, `.hdf5`, `.keras`, `.pb` | ❌ |
| ONNX | `.onnx` | ❌ |
| SafeTensors | `.safetensors` | ❌ |
| GGUF | `.gguf` | ❌ |

## Quick Start

```bash
# Clone repository
git clone <repository-url>
cd AI_model_scan

# Build and run with Docker
docker compose up --build -d

# Open web interface
open http://localhost:8080
```

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE` | 5368709120 (5GB) | Maximum upload file size (bytes) |
| `MAX_CONCURRENT_JOBS` | 2 | Concurrent job limit |
| `STRICT_POLICY_DEFAULT` | true | Default strict policy |
| `JOB_RETENTION_DAYS` | 30 | Job retention period (days) |
| `LOG_LEVEL` | INFO | Log level |

## API Usage

### Create Job

```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@model.pkl" \
  -F "enable_picklescan=true" \
  -F "strict_policy=true"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job created successfully"
}
```

### Check Status

```bash
curl http://localhost:8080/api/jobs/{job_id}
```

### Download Results

```bash
curl -o summary.json http://localhost:8080/api/jobs/{job_id}/download/summary.json
curl -o aisbom.json http://localhost:8080/api/jobs/{job_id}/download/aisbom.json
curl -o artifacts.zip http://localhost:8080/api/jobs/{job_id}/download/artifacts.zip
```

## Project Structure

```
AI_model_scan/
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration
│   ├── models.py         # Pydantic models
│   ├── scanner.py        # Scan tool execution
│   ├── job_manager.py    # Job management
│   └── utils.py          # Utilities
├── templates/            # HTML templates
├── static/               # CSS files
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── README_KO.md          # Korean documentation
├── INSTALL_OFFLINE.md    # Offline installation guide
├── INSTALL_OFFLINE_KO.md # Offline installation guide (Korean)
└── LICENSE
```

## Security Policy

### FAIL Conditions (strict_policy=true)

- ModelScan detects HIGH or CRITICAL vulnerability
- Picklescan detects dangerous global calls
- Malicious serialization code found

## Troubleshooting

### Container Won't Start

```bash
docker compose logs scanner
docker inspect ai-model-scanner | grep -A 10 Health
```

### Upload Failures

- Verify file size is within `MAX_UPLOAD_SIZE`
- Confirm file format is supported

### Permission Errors

```bash
chmod -R 755 ./data
```

## Documentation

- [Offline Installation Guide](INSTALL_OFFLINE.md)
- [한국어 문서](README_KO.md)
- [오프라인 설치 가이드](INSTALL_OFFLINE_KO.md)

## License

MIT License - See [LICENSE](LICENSE) for details.

## References

- [ModelScan](https://github.com/protectai/modelscan) - ML model security scanner
- [Picklescan](https://github.com/mmaitre314/picklescan) - Pickle file security scanner
