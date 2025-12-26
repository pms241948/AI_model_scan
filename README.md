# AI Model Security Scanner

A fully air-gapped web application for **AI/ML model file security scanning** and **AI-SBOM generation**.

## Features

| Feature | Description |
|---------|-------------|
| 🛡️ **Vulnerability Scanning** | ModelScan + Picklescan for security checks |
| 📋 **AI-SBOM Generation** | CycloneDX v1.6 format SBOM |
| 📦 **Archive Support** | ZIP, tar, tar.gz upload with auto-extraction |
| 📁 **Mounted Folder Scanning** | Scan models directly from mounted directories |
| 🌐 **Web UI** | Intuitive interface for upload, browse, and scan |
| 🔌 **REST API** | Full API for automation |
| 🔒 **Fully Offline** | 100% air-gapped operation |

## Supported Formats

### Model Files
| Format | Extensions | Picklescan |
|--------|------------|------------|
| PyTorch | `.pt`, `.pth`, `.bin` | ✅ |
| Pickle | `.pkl`, `.pickle`, `.joblib` | ✅ |
| SafeTensors | `.safetensors` | ❌ |
| GGUF | `.gguf` | ❌ |
| Keras | `.h5`, `.hdf5`, `.keras` | ❌ |
| ONNX | `.onnx` | ❌ |
| TensorFlow | `.pb`, `.tflite` | ❌ |

### Archive Files
| Format | Extensions |
|--------|------------|
| ZIP | `.zip` |
| TAR | `.tar` |
| GZIP TAR | `.tar.gz`, `.tgz` |

## Quick Start

```bash
# Clone and start
git clone <repository-url>
cd AI_model_scan
docker compose up --build -d

# Access web UI
open http://localhost:8080
```

## Usage

### 1. File Upload (Web UI)
- Navigate to http://localhost:8080
- Drag & drop model file or archive (ZIP/tar.gz)
- Configure scan options
- View results

### 2. Mounted Folder Scanning
Mount your model directory and scan without upload:

```yaml
# docker-compose.yml
volumes:
  - ./data:/data
  - /path/to/your/models:/models:ro  # Add your models path
```

Then browse http://localhost:8080/models to view and scan models.

### 3. REST API

**Create scan job:**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@model.safetensors" \
  -F "enable_picklescan=true" \
  -F "strict_policy=true"
```

**Upload archive:**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@models.tar.gz"
```

**Scan mounted model:**
```bash
curl -X POST http://localhost:8080/api/models/scan \
  -F "model_path=llama2-7b"
```

**Check status:**
```bash
curl http://localhost:8080/api/jobs/{job_id}
```

**Download results:**
```bash
curl -o summary.json http://localhost:8080/api/jobs/{job_id}/download/summary.json
curl -o aisbom.json http://localhost:8080/api/jobs/{job_id}/download/aisbom.json
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/jobs` | Create scan job (file upload) |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job status |
| `GET` | `/api/jobs/{id}/artifacts` | List artifacts |
| `GET` | `/api/jobs/{id}/download/{name}` | Download artifact |
| `DELETE` | `/api/jobs/{id}` | Delete job |
| `GET` | `/api/models` | List mounted models |
| `POST` | `/api/models/scan` | Scan mounted model |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE` | 0 (unlimited) | Max upload size in bytes |
| `MAX_CONCURRENT_JOBS` | 2 | Concurrent scan limit |
| `STRICT_POLICY_DEFAULT` | true | Fail on HIGH/CRITICAL |
| `MODELS_DIR` | /models | Mounted models directory |

## Project Structure

```
AI_model_scan/
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration
│   ├── models.py         # Pydantic models
│   ├── scanner.py        # Scan tools execution
│   ├── job_manager.py    # Job queue management
│   └── utils.py          # Utilities
├── templates/
│   ├── base.html         # Layout
│   ├── index.html        # Upload page
│   ├── models.html       # Mounted models browser
│   ├── jobs.html         # Job list
│   └── result.html       # Scan results
├── static/style.css      # Dark theme CSS
├── Dockerfile            # Multi-stage build
├── docker-compose.yml    # Service configuration
└── requirements.txt      # Dependencies
```

## Security Policy

### FAIL Conditions (strict_policy=true)
- ModelScan: HIGH or CRITICAL severity
- Picklescan: Dangerous globals detected
- Malicious deserialization code

### Output Artifacts
- `summary.json` - Scan summary with PASS/FAIL
- `modelscan.json` - ModelScan results
- `picklescan.json` - Picklescan results
- `aisbom.json` - CycloneDX v1.6 SBOM
- `artifacts.zip` - All results bundled

## Air-Gapped Deployment

See [INSTALL_OFFLINE.md](INSTALL_OFFLINE.md) for detailed instructions.

```bash
# Build (online)
docker compose build
docker save ai_model_scan-scanner:latest -o scanner.tar

# Deploy (offline)
docker load -i scanner.tar
docker compose up -d
```

## Documentation

- [한국어 문서](README_KO.md)
- [Offline Installation Guide](INSTALL_OFFLINE.md)
- [오프라인 설치 가이드](INSTALL_OFFLINE_KO.md)

## License

MIT License - See [LICENSE](LICENSE)

## References

- [ModelScan](https://github.com/protectai/modelscan)
- [Picklescan](https://github.com/mmaitre314/picklescan)
