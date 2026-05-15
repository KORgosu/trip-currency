# Trip Currency Service - 로컬 개발 환경

여행 환율 서비스 플랫폼의 애플리케이션 소스코드 및 로컬 개발 환경 저장소입니다.

---

## 목차

- [아키텍처](#아키텍처)
- [프로젝트 구조](#프로젝트-구조)
- [개발 환경 A: Docker Compose](#개발-환경-a-docker-compose)
- [개발 환경 B: Kubernetes (Docker Desktop)](#개발-환경-b-kubernetes-docker-desktop)
- [배포 가이드](#배포-가이드)
- [운영 및 관리](#운영-및-관리)
- [CI/CD 파이프라인](#cicd-파이프라인)
- [문제 해결](#문제-해결)

---

## 아키텍처

### 서비스 구성

| 서비스 | 언어/프레임워크 | 역할 |
|--------|--------------|------|
| service-frontend | React + Vite (Nginx) | 웹 UI |
| service-currency | FastAPI (Python) | 환율 조회 및 관리 |
| service-history | FastAPI (Python) | 환율 히스토리 |
| service-ranking | FastAPI (Python) | 환율 랭킹/통계 |
| service-dataingestor | FastAPI (Python) | 외부 환율 데이터 수집 (CronJob / Scheduler) |

### 인프라 구성

| 컴포넌트 | 로컬 (Compose) | 로컬 (K8s) | EKS (프로덕션) |
|---------|-------------|-----------|-------------|
| MySQL | Docker 컨테이너 | StatefulSet | Aurora MySQL |
| MongoDB | Docker 컨테이너 | StatefulSet | DocumentDB |
| Redis | Docker 컨테이너 | Deployment | ElastiCache |
| Kafka + Zookeeper | Docker 컨테이너 | ClusterIP | ClusterIP |
| kafka-ui | Docker 컨테이너 | ClusterIP | ClusterIP |

### 로컬 Kubernetes 트래픽 흐름

```
브라우저
  └─ NGINX Ingress Controller (MetalLB IP)
       ├─ trip-service.local          → service-frontend:80
       ├─ api.trip-service.local/currency → service-currency:8000
       ├─ api.trip-service.local/history  → service-history:8000
       └─ api.trip-service.local/ranking  → service-ranking:8000
```

### EKS 프로덕션

EKS 배포 매니페스트는 별도 GitOps 저장소(`trip-currency-local-gitops`)에서 관리합니다.

| URL | 용도 |
|-----|------|
| `https://2025teamproject.store` | 서비스 접속 |
| `https://grafana.2025teamproject.store` | Grafana 모니터링 |

---

## 프로젝트 구조

```
trip-currency-local/
├── frontend/                    # React + Vite 프론트엔드
│   ├── src/
│   │   ├── components/          # UI 컴포넌트 (common, country, currency, map, ranking)
│   │   ├── pages/               # HomePage, ComparisonPage
│   │   ├── hooks/               # useCurrencyData, useGeolocation, useRankingData
│   │   └── services/            # api.js (API 클라이언트)
│   ├── public/textures/         # 지구본 3D 텍스처 이미지
│   ├── Dockerfile
│   ├── nginx.conf
│   └── vite.config.js
│
├── service-currency/            # 환율 서비스 (FastAPI)
├── service-history/             # 히스토리 서비스 (FastAPI)
├── service-ranking/             # 랭킹 서비스 (FastAPI)
├── service-dataingestor/        # 데이터 수집 서비스 (FastAPI, CronJob)
├── package-shared/              # 공유 Python 패키지
│   └── shared/                  # config, database, messaging, models, logging, utils
│
├── scripts/                     # 초기화 및 빌드 스크립트
│   ├── init-db.sql              # MySQL 스키마 초기화
│   ├── init-mongodb.js          # MongoDB 초기화
│   ├── init-kafka-topics.sh     # Kafka 토픽 생성
│   ├── init_local_db.py         # 로컬 DB 데이터 초기화
│   ├── init_services.py         # 서비스 초기화
│   ├── rebuild-all.sh           # 전체 이미지 재빌드 (Linux/Mac)
│   ├── rebuild-all.ps1          # 전체 이미지 재빌드 (Windows)
│   └── start-dev-kube.ps1       # K8s 로컬 환경 시작 (Windows)
│
├── monitoring/                  # 로컬 모니터링 스택 (Docker Compose)
│   ├── docker-compose.yml       # Prometheus + Grafana + AlertManager
│   ├── prometheus/              # prometheus.yml, alert_rules.yml
│   ├── grafana/
│   │   ├── dashboards/          # kubernetes-cluster.json, trip-service.json
│   │   └── provisioning/        # datasources, dashboards 자동 설정
│   └── alertmanager/
│       └── alertmanager.yml
│
├── k8s/
│   ├── base/                    # 공통 Kubernetes 매니페스트
│   │   ├── kustomization.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml
│   │   ├── metallb/             # MetalLB IPAddressPool
│   │   ├── ingress/             # NGINX Ingress 규칙
│   │   ├── ingress-controller/  # NGINX Ingress Controller + RBAC
│   │   ├── mysql/               # deployment, service, pvc, configmap
│   │   ├── mongodb/             # deployment, service, pvc, configmap
│   │   ├── redis/               # deployment, service
│   │   ├── kafka/               # kafka, zookeeper, kafka-ui
│   │   ├── monitoring/          # prometheus-thanos-values, thanos-sidecar
│   │   └── services/
│   │       ├── frontend/        # deployment, service, hpa, configmap, ingress
│   │       ├── currency-service/ # deployment, service, hpa
│   │       ├── history-service/  # deployment, service, hpa
│   │       ├── ranking-service/  # deployment, service, hpa
│   │       └── dataingestor-service/ # cronjob
│   └── overlays/
│       ├── dev/                 # 로컬 개발 (namespace: trip-service-dev)
│       ├── staging/             # 로컬 스테이징
│       ├── prod/                # 로컬 프로덕션 (Jenkins 빌드 이미지)
│       └── eks/                 # EKS 전용 오버레이 (GitOps 레포로 이관됨)
│
├── Jenkinsfile                  # Jenkins CI/CD 파이프라인 (로컬 빌드)
├── Jenkinsfile.production       # Jenkins 프로덕션 파이프라인
├── docker-compose.yml           # 로컬 Docker Compose (전체 스택)
├── env.production               # 프로덕션 환경 변수
└── .env.example                 # 환경 변수 예시
```

---

## 개발 환경 A: Docker Compose

가장 빠르게 전체 스택을 로컬에서 실행하는 방법입니다.

### 사전 요구사항

- Docker Desktop

### 실행

```bash
docker compose up -d
```

### 포트 매핑

| 서비스 | 로컬 포트 | 컨테이너 포트 |
|--------|---------|------------|
| service-frontend | 3000 | 80 |
| service-currency | 8001 | 8000 |
| service-ranking | 8002 | 8000 |
| service-history | 8003 | 8000 |
| kafka-ui | 8081 | 8080 |
| MySQL | 3306 | 3306 |
| Redis | 6379 | 6379 |
| MongoDB | 27017 | 27017 |
| Kafka | 9092 | 9092 |
| Zookeeper | 2181 | 2181 |

### 로컬 모니터링 스택 (선택)

```bash
cd monitoring
docker compose up -d
```

Grafana: `http://localhost:3000` (admin / admin)

### 종료

```bash
docker compose down
# 볼륨까지 삭제하려면
docker compose down -v
```

---

## 개발 환경 B: Kubernetes (Docker Desktop)

Kubernetes 환경에서 실행하는 방법입니다.

### 사전 요구사항

- Docker Desktop (Kubernetes 활성화)
- kubectl
- 본인 IP 대역 확인: `ipconfig`

### 1단계: MetalLB IP Pool 설정

`k8s/base/metallb/ipaddresspool.yaml`의 `spec.addresses`를 본인 IP 대역으로 수정합니다.

```yaml
spec:
  addresses:
    - 192.168.X.100-192.168.X.110  # 본인 IP 대역으로 변경
```

Docker Desktop → Settings → Resources → Network → Subnet도 동일 대역으로 설정합니다.

### 2단계: MetalLB 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=90s
kubectl apply -f k8s/base/metallb/ipaddresspool.yaml
```

### 3단계: NGINX Ingress Controller 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s
```

### 4단계: 네임스페이스 및 Secrets 생성

```bash
kubectl create namespace trip-service-dev

kubectl apply -f k8s/base/secrets.yaml -n trip-service-dev
kubectl apply -f k8s/base/configmap.yaml -n trip-service-dev
```

### 5단계: 인프라 서비스 배포

```bash
kubectl apply -k k8s/base/mysql/ -n trip-service-dev
kubectl apply -k k8s/base/mongodb/ -n trip-service-dev
kubectl apply -k k8s/base/redis/ -n trip-service-dev
kubectl apply -k k8s/base/kafka/ -n trip-service-dev

kubectl wait --for=condition=ready pod -l app=mysql -n trip-service-dev --timeout=300s
kubectl wait --for=condition=ready pod -l app=mongodb -n trip-service-dev --timeout=300s
kubectl wait --for=condition=ready pod -l app=kafka -n trip-service-dev --timeout=300s
```

### 6단계: 이미지 빌드

```bash
docker build -f frontend/Dockerfile -t trip-service/service-frontend:dev-latest .
docker build -f service-currency/Dockerfile -t trip-service/service-currency:dev-latest .
docker build -f service-history/Dockerfile -t trip-service/service-history:dev-latest .
docker build -f service-ranking/Dockerfile -t trip-service/service-ranking:dev-latest .
docker build -f service-dataingestor/Dockerfile -t trip-service/service-dataingestor:dev-latest .
```

Windows에서는 `scripts/rebuild-all.ps1`을 사용할 수 있습니다.

### 7단계: 애플리케이션 배포

```bash
kubectl apply -k k8s/overlays/dev
kubectl get all -n trip-service-dev
```

### 8단계: hosts 파일 설정

`C:\Windows\System32\drivers\etc\hosts`에 추가 (관리자 권한 필요):

```
192.168.X.200 trip-service.local
192.168.X.200 api.trip-service.local
```

```bash
curl http://trip-service.local
curl http://api.trip-service.local/currency/health
```

---

## 배포 가이드

### 환경별 배포

| 명령어 | 환경 | 네임스페이스 |
|--------|------|------------|
| `kubectl apply -k k8s/overlays/dev` | 로컬 개발 | trip-service-dev |
| `kubectl apply -k k8s/overlays/staging` | 로컬 스테이징 | trip-service-staging |
| `kubectl apply -k k8s/overlays/prod` | 로컬 프로덕션 | trip-service-prod |

### 환경별 비교

| 항목 | Dev (Compose) | Dev (K8s) | EKS (Cloud) |
|------|-------------|----------|-------------|
| 레플리카 | 1 | 1 | 2~3 |
| 이미지 | 로컬 빌드 | 로컬 빌드 | AWS ECR |
| DB | 컨테이너 | StatefulSet | Aurora / DocumentDB / ElastiCache |
| Ingress | 없음 (포트 직접) | NGINX | AWS ALB |
| StorageClass | - | 기본값 | gp3-encrypted |
| 도메인 | localhost | trip-service.local | 2025teamproject.store |
| SSL/TLS | 없음 | 없음 | ACM |

---

## 운영 및 관리

### 파드 재시작

```bash
kubectl rollout restart deployment/service-currency -n trip-service-dev
kubectl rollout restart deployment/service-history -n trip-service-dev
kubectl rollout restart deployment/service-ranking -n trip-service-dev
kubectl rollout restart deployment/service-frontend -n trip-service-dev
```

### 상태 확인

```bash
# 전체 리소스
kubectl get all -n trip-service-dev

# 로그 확인
kubectl logs -l app=service-currency -n trip-service-dev --tail=50

# 이벤트 확인
kubectl get events -n trip-service-dev --sort-by='.lastTimestamp'

# HPA 상태
kubectl get hpa -n trip-service-dev
```

### 데이터 확인

```bash
# MySQL
kubectl exec -it $(kubectl get pod -l app=mysql -n trip-service-dev -o jsonpath='{.items[0].metadata.name}') \
  -n trip-service-dev -- mysql -u root -p -e "USE currency_db; SELECT COUNT(*) FROM exchange_rate_history;"

# Redis
kubectl exec -it $(kubectl get pod -l app=redis -n trip-service-dev -o jsonpath='{.items[0].metadata.name}') \
  -n trip-service-dev -- redis-cli KEYS "*"
```

---

## CI/CD 파이프라인

### Jenkins 파이프라인 (Jenkinsfile.production)

```
Git Push → Jenkins 웹훅 트리거
  → Build & Test (서비스별 단위 테스트, 병렬)
  → Docker Build & Push (ECR + Docker Hub, 병렬)
  → SBOM & Vulnerability Scan (Trivy, 병렬)
       ├─ CycloneDX SBOM 생성 → Jenkins 아티팩트 보관
       └─ CRITICAL 취약점 발견 시 파이프라인 중단
  → Update GitOps Repository (이미지 태그 업데이트 → ArgoCD 자동 배포)
```

### SBOM 및 이미지 보안

| 항목 | 도구 | 내용 |
|------|------|------|
| SBOM 생성 | Trivy | CycloneDX JSON 포맷, 서비스별 `sbom-{서비스}.json` |
| 취약점 스캔 | Trivy | CRITICAL + 패치 버전 존재 시 배포 차단 (`--ignore-unfixed`) |
| ECR 자동 스캔 | AWS Inspector v2 | Push 시 + 신규 CVE 발표 시 자동 재스캔 (CONTINUOUS_SCAN) |

### ECR 로그인

```bash
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin 716773066105.dkr.ecr.ap-northeast-2.amazonaws.com
```

### 이미지 태그 규칙

| 환경 | 태그 | 레지스트리 |
|------|------|----------|
| 개발 | `dev-latest` | 로컬 빌드 |
| 스테이징 | `staging-latest` | 로컬 빌드 |
| 프로덕션 | `latest` | AWS ECR |

---

## 문제 해결

### Pod가 시작되지 않음

```bash
kubectl describe pod <pod-name> -n trip-service-dev
kubectl logs <pod-name> -n trip-service-dev
```

### 데이터베이스 연결 실패

```bash
kubectl get secret -n trip-service-dev          # Secrets 생성 여부
kubectl get statefulset -n trip-service-dev     # DB StatefulSet 상태
kubectl get pvc -n trip-service-dev             # PVC 바인딩 여부
```

### Ingress 접속 불가

```bash
# MetalLB IP 할당 확인
kubectl get svc -n ingress-nginx

# Ingress 규칙 확인
kubectl get ingress -n trip-service-dev -o yaml
```

### HPA가 동작하지 않음

로컬 환경에서는 metrics-server가 필요합니다:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl get hpa -n trip-service-dev
```

EKS 환경에서는 Prometheus Adapter를 통해 custom metrics를 HPA에 공급합니다.

---

## 접속 URL 요약

| 환경 | URL |
|------|-----|
| 로컬 Compose 프론트엔드 | `http://localhost:3000` |
| 로컬 Compose API (currency) | `http://localhost:8001` |
| 로컬 K8s 프론트엔드 | `http://trip-service.local` |
| 로컬 K8s API | `http://api.trip-service.local` |
| 로컬 모니터링 Grafana | `http://localhost:3000` (monitoring/docker-compose.yml 실행 시) |
| EKS 프로덕션 | `https://2025teamproject.store` |
| EKS Grafana | `https://grafana.2025teamproject.store` |
