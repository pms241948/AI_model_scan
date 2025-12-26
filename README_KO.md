# AI 모델 보안 스캐너

완전 폐쇄망(Air-gapped) 환경에서 동작하는 **AI/ML 모델 파일 보안 스캔** 및 **AI-SBOM 생성** 웹 애플리케이션입니다.

## 주요 기능

- 🛡️ **취약성 스캔**: ModelScan, Picklescan을 활용한 모델 파일 보안 검사
- 📋 **AI-SBOM 생성**: CycloneDX v1.6 형식의 SBOM 자동 생성
- 🌐 **WebUI 제공**: 직관적인 파일 업로드 및 결과 확인 인터페이스
- 🔌 **REST API**: 자동화를 위한 API 엔드포인트 제공
- 🔒 **완전 오프라인**: 외부 네트워크 연결 없이 100% 동작

## 지원 모델 형식

| 형식 | 확장자 | Picklescan 지원 |
|------|--------|-----------------|
| PyTorch | `.pt`, `.pth`, `.bin` | ✅ |
| Pickle | `.pkl`, `.pickle`, `.joblib` | ✅ |
| Keras/TF | `.h5`, `.hdf5`, `.keras`, `.pb` | ❌ |
| ONNX | `.onnx` | ❌ |
| SafeTensors | `.safetensors` | ❌ |
| GGUF | `.gguf` | ❌ |

## 빠른 시작 (온라인 환경)

```bash
# 저장소 클론
git clone <repository-url>
cd AI_model_scan

# Docker 이미지 빌드 및 실행
docker compose up --build -d

# 웹 브라우저에서 접속
open http://localhost:8080
```

## 환경 설정

`docker-compose.yml`에서 다음 환경 변수를 설정할 수 있습니다:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MAX_UPLOAD_SIZE` | 5368709120 (5GB) | 최대 업로드 파일 크기 (바이트) |
| `MAX_CONCURRENT_JOBS` | 2 | 동시 처리 작업 수 |
| `STRICT_POLICY_DEFAULT` | true | 엄격 정책 기본값 |
| `JOB_RETENTION_DAYS` | 30 | 작업 보관 기간 (일) |
| `LOG_LEVEL` | INFO | 로그 레벨 |

## API 사용법

### 작업 생성

```bash
curl -X POST http://localhost:8080/api/jobs \
  -F "file=@model.pkl" \
  -F "enable_picklescan=true" \
  -F "strict_policy=true"
```

**응답:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job created successfully"
}
```

### 작업 상태 조회

```bash
curl http://localhost:8080/api/jobs/{job_id}
```

### 결과 다운로드

```bash
# 요약 결과
curl -o summary.json http://localhost:8080/api/jobs/{job_id}/download/summary.json

# AI-SBOM
curl -o aisbom.json http://localhost:8080/api/jobs/{job_id}/download/aisbom.json

# 전체 결과 ZIP
curl -o artifacts.zip http://localhost:8080/api/jobs/{job_id}/download/artifacts.zip
```

## 프로젝트 구조

```
AI_model_scan/
├── app/
│   ├── main.py           # FastAPI 애플리케이션
│   ├── config.py         # 설정 관리
│   ├── models.py         # Pydantic 모델
│   ├── scanner.py        # 스캔 도구 실행
│   ├── job_manager.py    # 작업 관리
│   └── utils.py          # 유틸리티
├── templates/            # HTML 템플릿
├── static/               # CSS 파일
├── data/                 # 데이터 볼륨
│   ├── uploads/          # 업로드 파일
│   ├── results/          # 스캔 결과
│   └── logs/             # 로그
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 보안 정책

### FAIL 조건 (strict_policy=true)

- ModelScan에서 HIGH 또는 CRITICAL 취약점 탐지
- Picklescan에서 위험한 글로벌 호출 탐지
- 악성 직렬화 코드 발견

### 결과 요약 (summary.json)

```json
{
  "job_id": "...",
  "filename": "model.pkl",
  "sha256": "...",
  "pass_fail": "FAIL",
  "fail_reason": "ModelScan: HIGH - Unsafe deserialization detected",
  "total_findings": 3,
  "findings_by_severity": {
    "HIGH": 2,
    "MEDIUM": 1
  }
}
```

## 문제 해결

### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker compose logs scanner

# 헬스체크 상태 확인
docker inspect ai-model-scanner | grep -A 10 Health
```

### 파일 업로드 실패

- 파일 크기가 `MAX_UPLOAD_SIZE`를 초과하지 않는지 확인
- 지원되는 파일 형식인지 확인

### 권한 오류

```bash
chmod -R 755 ./data
```

## 문서

- [오프라인 설치 가이드](INSTALL_OFFLINE_KO.md)
- [English Documentation](README.md)
- [Offline Installation Guide](INSTALL_OFFLINE.md)

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

## 참고 도구

- [ModelScan](https://github.com/protectai/modelscan) - ML 모델 보안 스캐너
- [Picklescan](https://github.com/mmaitre314/picklescan) - Pickle 파일 보안 스캐너
