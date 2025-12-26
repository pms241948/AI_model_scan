# AI 모델 보안 스캐너

완전 폐쇄망(Air-gapped) 환경에서 동작하는 **AI/ML 모델 파일 보안 스캔** 및 **AI-SBOM 생성** 웹 애플리케이션입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🛡️ **취약점 스캔** | ModelScan + Picklescan 보안 검사 |
| 📋 **AI-SBOM 생성** | CycloneDX v1.6 형식 SBOM |
| 📦 **아카이브 지원** | ZIP, tar, tar.gz 업로드 및 자동 압축 해제 |
| 📁 **마운트 폴더 스캔** | 업로드 없이 마운트된 디렉터리에서 직접 스캔 |
| 🌐 **웹 UI** | 업로드, 조회, 스캔을 위한 직관적 인터페이스 |
| 🔌 **REST API** | 자동화를 위한 API 제공 |
| 🔒 **완전 오프라인** | 100% 폐쇄망 동작 |

## 지원 형식

### 모델 파일
| 형식 | 확장자 | Picklescan |
|------|--------|------------|
| PyTorch | `.pt`, `.pth`, `.bin` | ✅ |
| Pickle | `.pkl`, `.pickle`, `.joblib` | ✅ |
| SafeTensors | `.safetensors` | ❌ |
| GGUF | `.gguf` | ❌ |
| Keras | `.h5`, `.hdf5`, `.keras` | ❌ |
| ONNX | `.onnx` | ❌ |
| TensorFlow | `.pb`, `.tflite` | ❌ |

### 아카이브 파일
| 형식 | 확장자 |
|------|--------|
| ZIP | `.zip` |
| TAR | `.tar` |
| GZIP TAR | `.tar.gz`, `.tgz` |

## 빠른 시작

```bash
# 클론 및 시작
git clone <repository-url>
cd AI_model_scan
docker compose up --build -d

# 웹 UI 접속
open http://localhost:8080
```

## 사용 방법

### 1. 파일 업로드 (웹 UI)
- http://localhost:8080 접속
- 모델 파일 또는 아카이브(ZIP/tar.gz) 드래그 & 드롭
- 스캔 옵션 설정
- 결과 확인

### 2. 마운트 폴더 스캔
모델 디렉터리를 마운트하여 업로드 없이 스캔:

```yaml
# docker-compose.yml
volumes:
  - ./data:/data
  - /path/to/your/models:/models:ro  # 모델 경로 추가
```

http://localhost:8080/models 에서 모델 조회 및 스캔 가능.

### 3. REST API

**스캔 작업 생성:**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@model.safetensors" \
  -F "enable_picklescan=true" \
  -F "strict_policy=true"
```

**아카이브 업로드:**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@models.tar.gz"
```

**마운트된 모델 스캔:**
```bash
curl -X POST http://localhost:8080/api/models/scan \
  -F "model_path=llama2-7b"
```

**상태 확인:**
```bash
curl http://localhost:8080/api/jobs/{job_id}
```

**결과 다운로드:**
```bash
curl -o summary.json http://localhost:8080/api/jobs/{job_id}/download/summary.json
curl -o aisbom.json http://localhost:8080/api/jobs/{job_id}/download/aisbom.json
```

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/health` | 헬스 체크 |
| `POST` | `/api/jobs` | 스캔 작업 생성 (파일 업로드) |
| `GET` | `/api/jobs` | 작업 목록 조회 |
| `GET` | `/api/jobs/{id}` | 작업 상태 조회 |
| `GET` | `/api/jobs/{id}/artifacts` | 결과 파일 목록 |
| `GET` | `/api/jobs/{id}/download/{name}` | 결과 파일 다운로드 |
| `DELETE` | `/api/jobs/{id}` | 작업 삭제 |
| `GET` | `/api/models` | 마운트된 모델 목록 |
| `POST` | `/api/models/scan` | 마운트된 모델 스캔 |

## 환경 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MAX_UPLOAD_SIZE` | 0 (무제한) | 최대 업로드 크기 (바이트) |
| `MAX_CONCURRENT_JOBS` | 2 | 동시 스캔 작업 수 |
| `STRICT_POLICY_DEFAULT` | true | HIGH/CRITICAL 시 FAIL |
| `MODELS_DIR` | /models | 마운트된 모델 디렉터리 |

## 프로젝트 구조

```
AI_model_scan/
├── app/
│   ├── main.py           # FastAPI 애플리케이션
│   ├── config.py         # 설정 관리
│   ├── models.py         # Pydantic 모델
│   ├── scanner.py        # 스캔 도구 실행
│   ├── job_manager.py    # 작업 큐 관리
│   └── utils.py          # 유틸리티
├── templates/
│   ├── base.html         # 레이아웃
│   ├── index.html        # 업로드 페이지
│   ├── models.html       # 마운트 모델 브라우저
│   ├── jobs.html         # 작업 목록
│   └── result.html       # 스캔 결과
├── static/style.css      # 다크 테마 CSS
├── Dockerfile            # 멀티 스테이지 빌드
├── docker-compose.yml    # 서비스 설정
└── requirements.txt      # 의존성
```

## 보안 정책

### FAIL 조건 (strict_policy=true)
- ModelScan: HIGH 또는 CRITICAL 심각도
- Picklescan: 위험한 글로벌 탐지
- 악성 역직렬화 코드

### 출력 결과물
- `summary.json` - PASS/FAIL 스캔 요약
- `modelscan.json` - ModelScan 결과
- `picklescan.json` - Picklescan 결과
- `aisbom.json` - CycloneDX v1.6 SBOM
- `artifacts.zip` - 모든 결과 번들

## 폐쇄망 배포

자세한 내용은 [INSTALL_OFFLINE_KO.md](INSTALL_OFFLINE_KO.md) 참조.

```bash
# 빌드 (온라인)
docker compose build
docker save ai_model_scan-scanner:latest -o scanner.tar

# 배포 (오프라인)
docker load -i scanner.tar
docker compose up -d
```

## vLLM 모델 스캔 예시

```yaml
# docker-compose.yml 수정
volumes:
  - ./data:/data
  - /home/user/.cache/huggingface:/models:ro  # Hugging Face 캐시
  # 또는
  - /opt/vllm/models:/models:ro               # vLLM 모델 경로
```

```bash
docker compose up -d
# http://localhost:8080/models 에서 모델 확인 및 스캔
```

## 문서

- [English Documentation](README.md)
- [Offline Installation Guide](INSTALL_OFFLINE.md)
- [오프라인 설치 가이드](INSTALL_OFFLINE_KO.md)

## 라이선스

MIT License - [LICENSE](LICENSE) 참조

## 참고 도구

- [ModelScan](https://github.com/protectai/modelscan)
- [Picklescan](https://github.com/mmaitre314/picklescan)
