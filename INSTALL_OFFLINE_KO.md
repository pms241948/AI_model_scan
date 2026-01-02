# 오프라인 설치 가이드

이 문서는 **폐쇄망(Air-gapped) 환경**에서 AI 모델 보안 스캐너를 배포하는 방법을 설명합니다.

## 개요

폐쇄망 환경은 인터넷에 접근할 수 없으므로 다음 단계를 수행해야 합니다:
1. 인터넷이 연결된 머신에서 Docker 이미지 빌드
2. 이미지를 파일로 내보내기
3. 파일을 폐쇄망 환경으로 전송
4. 이미지를 가져와서 실행

---

## 사전 요구사항

### 소스 머신 (인터넷 연결)
- Docker Engine 20.10 이상
- Docker Compose v2 이상
- Git (선택사항)
- 최소 5GB 여유 디스크 공간

### 대상 머신 (폐쇄망)
- Docker Engine 20.10 이상
- Docker Compose v2 이상
- 최소 3GB 여유 디스크 공간

---

## 1단계: 인터넷 연결된 머신에서 준비

### 1.1 소스 코드 준비

```bash
# 저장소 클론 (또는 파일 수동 복사)
git clone <repository-url>
cd AI_model_scan
```

### 1.2 Docker 이미지 빌드

```bash
# 이미지 빌드
docker compose build

# 이미지 생성 확인
docker images | grep ai_model_scan
```

예상 출력:
```
ai_model_scan-scanner   latest   abc123def456   2 minutes ago   420MB
```

### 1.3 이미지를 파일로 내보내기

```bash
# tar 파일로 이미지 저장
docker save ai_model_scan-scanner:latest -o ai-model-scanner.tar

# 파일 크기 확인
ls -lh ai-model-scanner.tar
```

tar 파일 크기는 약 **400~500MB**입니다.

### 1.4 전송 패키지 준비

필요한 모든 파일을 포함한 전송 패키지 생성:

```bash
# 전송 디렉터리 생성
mkdir -p transfer-package

# 필수 파일 복사
cp ai-model-scanner.tar transfer-package/
cp docker-compose.yml transfer-package/

# 아카이브 생성 (선택사항)
tar -czvf ai-model-scanner-package.tar.gz transfer-package/
```

---

## 2단계: 폐쇄망 환경으로 전송

승인된 매체를 사용하여 다음 파일들을 대상 머신으로 전송:
- USB 드라이브
- 보안 파일 전송
- CD/DVD
- 보안 정책에 따른 기타 승인된 방법

**필수 파일:**
- `ai-model-scanner.tar` (Docker 이미지)
- `docker-compose.yml` (설정 파일)

---

## 3단계: 폐쇄망 머신에서 배포

### 3.1 Docker 이미지 로드

```bash
# 전송된 파일 위치로 이동
cd /path/to/transferred/files

# Docker 이미지 로드
docker load -i ai-model-scanner.tar
```

예상 출력:
```
Loaded image: ai_model_scan-scanner:latest
```

### 3.2 이미지 확인

```bash
docker images | grep ai_model_scan
```

### 3.3 데이터 디렉터리 생성

```bash
# 영구 데이터 디렉터리 생성
mkdir -p ./data
chmod 755 ./data
```

### 3.4 애플리케이션 시작

```bash
# Docker Compose로 시작
docker compose up -d

# 상태 확인
docker compose ps
```

예상 출력:
```
NAME                COMMAND                  SERVICE    STATUS    PORTS
ai-model-scanner    "python -m uvicorn..."   scanner    Up        0.0.0.0:8080->8080/tcp
```

### 3.5 헬스 체크

```bash
# 헬스 엔드포인트 확인
curl http://localhost:8080/health
```

예상 응답:
```json
{"status":"healthy","service":"ai-model-scanner"}
```

---

## 4단계: 애플리케이션 접속

웹 브라우저에서 다음 주소로 접속:
```
http://localhost:8080
```

또는 네트워크의 다른 머신에서 접속하는 경우:
```
http://<서버-IP>:8080
```

---

## 문제 해결

### 이미지 로드 실패

```bash
# Docker 데몬 실행 확인
systemctl status docker

# 디스크 공간 확인
df -h
```

### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker compose logs -f

# 포트 충돌 확인
netstat -tlnp | grep 8080
```

### 권한 문제

```bash
# 데이터 디렉터리 권한 수정
sudo chown -R 1000:1000 ./data
chmod -R 755 ./data
```

### 헬스 체크 실패

```bash
# 시작 대기 (최대 30초)
sleep 30
curl http://localhost:8080/health

# 컨테이너 로그 확인
docker compose logs scanner
```

---

## 애플리케이션 업데이트

폐쇄망 환경에서 애플리케이션을 업데이트하려면:

1. 인터넷 연결된 머신에서 새 이미지 빌드
2. `docker save`로 내보내기
3. 폐쇄망 환경으로 전송
4. 현재 컨테이너 중지: `docker compose down`
5. 새 이미지 로드: `docker load -i new-image.tar`
6. 업데이트된 컨테이너 시작: `docker compose up -d`

---

## 보안 고려사항

- 애플리케이션은 컨테이너 내부에서 비루트 사용자로 실행됩니다
- 런타임에 외부 네트워크 호출이 없습니다
- 모든 의존성이 Docker 이미지에 번들되어 있습니다
- 업로드된 파일은 마운트된 `./data` 볼륨에 저장됩니다
- 컨테이너에 대한 네트워크 격리 구현을 고려하세요

---

## 파일 체크섬

배포 전 파일 무결성 검증:

```bash
# 체크섬 생성 (소스 머신에서)
sha256sum ai-model-scanner.tar > checksums.txt
sha256sum docker-compose.yml >> checksums.txt

# 체크섬 검증 (대상 머신에서)
sha256sum -c checksums.txt
```

---

## 빠른 참조

| 단계 | 명령어 |
|------|--------|
| 이미지 빌드 | `docker compose build` |
| 이미지 저장 | `docker save ai_model_scan-scanner:latest -o ai-model-scanner.tar` |
| 이미지 로드 | `docker load -i ai-model-scanner.tar` |
| 서비스 시작 | `docker compose up -d` |
| 서비스 중지 | `docker compose down` |
| 로그 확인 | `docker compose logs -f` |
| 헬스 체크 | `curl http://localhost:8080/health` |
