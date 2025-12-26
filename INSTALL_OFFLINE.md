# Offline Installation Guide

This guide explains how to deploy the AI Model Security Scanner in an **air-gapped (offline) environment**.

## Overview

Since the target environment has no internet access, you must:
1. Build the Docker image on an internet-connected machine
2. Export the image to a file
3. Transfer the file to the air-gapped environment
4. Import and run the image

---

## Prerequisites

### Source Machine (Internet Access)
- Docker Engine 20.10+
- Docker Compose v2+
- Git (optional)
- At least 5GB free disk space

### Target Machine (Air-Gapped)
- Docker Engine 20.10+
- Docker Compose v2+
- At least 3GB free disk space

---

## Step 1: Prepare on Internet-Connected Machine

### 1.1 Get the Source Code

```bash
# Clone repository (or copy files manually)
git clone <repository-url>
cd AI_model_scan
```

### 1.2 Build Docker Image

```bash
# Build the image
docker compose build

# Verify the image was created
docker images | grep ai_model_scan
```

Expected output:
```
ai_model_scan-scanner   latest   abc123def456   2 minutes ago   1.2GB
```

### 1.3 Export Image to File

```bash
# Save image as tar file
docker save ai_model_scan-scanner:latest -o ai-model-scanner.tar

# Verify file size
ls -lh ai-model-scanner.tar
```

The tar file will be approximately **1-1.5GB**.

### 1.4 Prepare Transfer Package

Create a transfer package with all necessary files:

```bash
# Create transfer directory
mkdir -p transfer-package

# Copy required files
cp ai-model-scanner.tar transfer-package/
cp docker-compose.yml transfer-package/
cp -r static transfer-package/  # Optional: if mounting externally
cp -r templates transfer-package/  # Optional: if mounting externally

# Create archive (optional)
tar -czvf ai-model-scanner-package.tar.gz transfer-package/
```

---

## Step 2: Transfer to Air-Gapped Environment

Transfer the following files to the target machine using approved media:
- USB drive
- Secure file transfer
- CD/DVD
- Other approved methods per your security policy

**Required files:**
- `ai-model-scanner.tar` (Docker image)
- `docker-compose.yml` (Configuration)

---

## Step 3: Deploy on Air-Gapped Machine

### 3.1 Load Docker Image

```bash
# Navigate to transfer location
cd /path/to/transferred/files

# Load the Docker image
docker load -i ai-model-scanner.tar
```

Expected output:
```
Loaded image: ai_model_scan-scanner:latest
```

### 3.2 Verify Image

```bash
docker images | grep ai_model_scan
```

### 3.3 Create Data Directory

```bash
# Create persistent data directory
mkdir -p ./data
chmod 755 ./data
```

### 3.4 Start the Application

```bash
# Start with Docker Compose
docker compose up -d

# Check status
docker compose ps
```

Expected output:
```
NAME                COMMAND                  SERVICE    STATUS    PORTS
ai-model-scanner    "python -m uvicorn..."   scanner    Up        0.0.0.0:8080->8080/tcp
```

### 3.5 Verify Health

```bash
# Check health endpoint
curl http://localhost:8080/health
```

Expected response:
```json
{"status":"healthy","service":"ai-model-scanner"}
```

---

## Step 4: Access the Application

Open a web browser and navigate to:
```
http://localhost:8080
```

Or if accessing from another machine on the network:
```
http://<server-ip>:8080
```

---

## Troubleshooting

### Image Load Fails

```bash
# Check Docker daemon is running
systemctl status docker

# Check disk space
df -h
```

### Container Won't Start

```bash
# View logs
docker compose logs -f

# Check for port conflicts
netstat -tlnp | grep 8080
```

### Permission Issues

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 ./data
chmod -R 755 ./data
```

### Health Check Fails

```bash
# Wait for startup (up to 30 seconds)
sleep 30
curl http://localhost:8080/health

# Check container logs
docker compose logs scanner
```

---

## Updating the Application

To update the application in an air-gapped environment:

1. Build new image on internet-connected machine
2. Export with `docker save`
3. Transfer to air-gapped environment
4. Stop current container: `docker compose down`
5. Load new image: `docker load -i new-image.tar`
6. Start updated container: `docker compose up -d`

---

## Security Considerations

- The application runs as non-root user inside the container
- No external network calls are made at runtime
- All dependencies are bundled in the Docker image
- Uploaded files are stored in the mounted `./data` volume
- Consider implementing network isolation for the container

---

## File Checksums

Before deployment, verify file integrity:

```bash
# Generate checksums (on source machine)
sha256sum ai-model-scanner.tar > checksums.txt
sha256sum docker-compose.yml >> checksums.txt

# Verify checksums (on target machine)
sha256sum -c checksums.txt
```
