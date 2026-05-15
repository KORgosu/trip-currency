# Trip Currency Service - GitOps Repository

여행 환율 서비스 플랫폼의 Kubernetes 매니페스트 및 AWS 인프라 설정을 관리하는 저장소입니다.

---

## 목차

- [개요](#개요)
- [현재 운영 환경](#현재-운영-환경)
- [디렉토리 구조](#디렉토리-구조)
- [민감 데이터 관리](#민감-데이터-관리)
- [EKS 인프라 구성](#eks-인프라-구성)
- [모니터링 및 로깅](#모니터링-및-로깅)
- [네트워크 보안](#네트워크-보안)
- [공급망 보안 (SBOM)](#공급망-보안-sbom)
- [배포 가이드](#배포-가이드)
- [잔여 보안 조치](#잔여-보안-조치)

---

## 개요

이 저장소는 **GitOps** 방식으로 AWS EKS 클러스터에 배포되는 Trip Currency Service의 모든 매니페스트와 AWS CLI 입력 파일을 관리합니다.

- **Kustomize 기반**: base + overlay 구조로 환경별 설정 분리
- **EKS Overlay**: 실제 운영 중인 AWS EKS 환경 (`ap-northeast-2`)
- **AWS 인프라 파일**: IAM, EKS, Route53, ACM 설정 파일 버전 관리
- **민감 데이터 분리**: 실제 값은 `.gitignore` 처리, 템플릿/example 파일만 커밋

---

## 현재 운영 환경

### 접속 주소

| 서비스 | URL |
|--------|-----|
| 메인 서비스 | `https://2025teamproject.store` |
| Grafana | `https://grafana.2025teamproject.store` |

### 클러스터 현황

| 항목 | 값 |
|------|-----|
| 클러스터명 | trip-service-cluster |
| Kubernetes 버전 | v1.33 |
| 리전 | ap-northeast-2 (서울) |
| 노드 그룹 | trip-service-workers (t3.medium x 3, min:2 / max:5) |
| max-pods | 110 (VPC Prefix Delegation + NodeConfig) |
| 노드 OS | Amazon Linux 2023 |
| 컨트롤 플레인 로깅 | api, audit, authenticator, controllerManager, scheduler |

### 아키텍처 다이어그램

```
인터넷
  ├─ Route53: 2025teamproject.store         (A Alias) ─┐
  └─ Route53: grafana.2025teamproject.store (A Alias) ─┤
                                                        ▼
                              ALB: trip-service-alb (internet-facing)
                              IngressGroup: trip-service
                              HTTP:80 → HTTPS:443 리다이렉트
                              ACM: *.2025teamproject.store
                                        │
              ┌─────────────────────────┼──────────────────────────────┐
              │ VPC: 192.168.0.0/16     │                              │
              │                         │                              │
              │  ┌── EKS trip-service-cluster (v1.33, ap-northeast-2) ─┐
              │  │                                                      │
              │  │  [trip-service-prod]        NetworkPolicy: 적용됨    │
              │  │  service-frontend  (ClusterIP :80)                  │
              │  │  service-currency  (ClusterIP :8000)                │
              │  │  service-history   (ClusterIP :8000)                │
              │  │  service-ranking   (ClusterIP :8000)                │
              │  │  kafka             (ClusterIP :9092)                │
              │  │  kafka-ui          (ClusterIP :8080, ingress 차단)  │
              │  │  zookeeper         (ClusterIP :2181)                │
              │  │  service-dataingestor (CronJob */5 * * * *)         │
              │  │                                                      │
              │  │  [monitoring]       Grafana ← ALB Ingress           │
              │  │  Prometheus (20Gi) │ Grafana (5Gi) │ AlertManager   │
              │  │  node-exporter (x3) │ kube-state-metrics            │
              │  │                                                      │
              │  │  [logging]                                           │
              │  │  Fluent Bit DaemonSet → CloudWatch Logs              │
              │  │                                                      │
              │  │  [kube-system]                                       │
              │  │  ALB Controller │ External Secrets │ CoreDNS         │
              │  │  aws-node (VPC CNI, Prefix Delegation, max-pods:110)│
              │  │  Calico (policy-engine) │ EBS CSI Driver            │
              │  └──────────────────────────────────────────────────────┘
              │                                                          │
              │  Aurora MySQL │ DocumentDB │ ElastiCache Redis           │
              │  (VPC 내부 접근만 허용, SG: 192.168.0.0/16)             │
              └──────────────────────────────────────────────────────────┘

CloudWatch Logs:
  /eks/trip-service-cluster/applications  (trip-service-prod, 30일)
  /eks/trip-service-cluster/infra         (monitoring, 14일)
  /eks/trip-service-cluster/host          (kubelet/systemd, 14일)
  /aws/eks/trip-service-cluster/cluster   (EKS 컨트롤 플레인 감사 로그)
```

---

## 디렉토리 구조

```
trip-currency-local-gitops/
├── .gitignore                             # 민감 파일 제외 목록
├── .env.aws.example                       # AWS 인프라 변수 예시 (실제 값 포함)
│
├── k8s/
│   ├── base/                              # 공통 매니페스트
│   │   ├── kustomization.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml
│   │   ├── kafka/                         # Kafka, Zookeeper, kafka-ui
│   │   ├── redis/                         # Deployment + Service
│   │   ├── mysql/                         # StatefulSet + Headless Service
│   │   ├── mongodb/                       # StatefulSet + Headless Service
│   │   ├── metallb/                       # IPAddressPool (로컬 K8s용)
│   │   ├── ingress/                       # NGINX Ingress 규칙 (로컬 K8s용)
│   │   ├── ingress-controller/            # NGINX Controller + RBAC (로컬 K8s용)
│   │   └── services/
│   │       ├── currency-service/          # Deployment, Service, HPA
│   │       ├── history-service/           # Deployment, Service, HPA
│   │       ├── ranking-service/           # Deployment, Service, HPA
│   │       ├── dataingestor-service/      # CronJob
│   │       └── frontend/                  # Deployment, Service, HPA, ConfigMap
│   │
│   └── overlays/
│       ├── dev/                           # 로컬 개발 환경 (NGINX Ingress)
│       ├── staging/
│       ├── prod/                          # 로컬 프로덕션 (NGINX Ingress)
│       └── eks/                           # AWS EKS 프로덕션 환경
│           ├── kustomization.yaml         # ECR 이미지 패치, AWS ConfigMap 패치
│           ├── namespace.yaml
│           ├── ingress.yaml               # ALB Ingress (trip-service-prod)
│           ├── storageclass.yaml          # gp3-encrypted StorageClass
│           ├── iam-policy-external-secrets.json  # External Secrets IAM 정책
│           ├── calico/
│           │   └── installation.yaml      # Calico Tigera Operator (AmazonVPC mode)
│           ├── external-secrets/
│           │   ├── cluster-secret-store.yaml
│           │   ├── external-secret.yaml
│           │   └── kustomization.yaml
│           ├── monitoring/
│           │   ├── kube-prometheus-stack-values.yaml  # Helm values (adminPassword 제거됨)
│           │   ├── grafana-ingress.yaml   # grafana.2025teamproject.store ALB Ingress
│           │   └── grafana-admin-secret.yaml.example  # Grafana admin Secret 예시
│           ├── logging/
│           │   └── fluent-bit-values.yaml # Fluent Bit Helm values → CloudWatch Logs
│           └── network-policies/
│               ├── 00-default-deny.yaml
│               ├── 01-allow-dns.yaml
│               ├── 02-frontend.yaml
│               ├── 03-currency.yaml
│               ├── 04-history.yaml
│               ├── 05-ranking.yaml
│               ├── 06-dataingestor.yaml
│               ├── 07-kafka.yaml
│               ├── 08-kafka-ui.yaml
│               ├── 09-zookeeper.yaml
│               └── 10-allow-prometheus-scrape.yaml
│
├── aws/                                   # AWS CLI 입력 파일
│   ├── eks/
│   │   ├── cluster-config.yaml.template   # eksctl ClusterConfig (플레이스홀더)
│   │   ├── logging-config.json            # 컨트롤 플레인 로깅 활성화 설정
│   │   └── lt-userdata.json               # Launch Template v2 user data (maxPods:110)
│   ├── iam/
│   │   ├── alb-policy-v2.json             # ALB Controller IAM 정책 v2
│   │   ├── alb-policy-v3.json             # ALB Controller IAM 정책 v3 (현재 적용)
│   │   └── ebs-csi-trust.json.template    # EBS CSI IRSA 신뢰 정책 (플레이스홀더)
│   ├── route53/                           # .gitignore — 일회성 파일, 재사용 불필요
│   │   ├── main-domain.json
│   │   └── grafana-domain.json
│   └── acm/                              # .gitignore — DNS 검증 완료, 재사용 불필요
│       └── validation.json
│
└── README.md
```

> `aws/route53/`, `aws/acm/` 디렉토리는 `.gitignore`로 제외됩니다 (일회성 적용 파일).

---

## 민감 데이터 관리

### .gitignore 처리 항목

| 파일/디렉토리 | 이유 |
|-------------|------|
| `aws/iam/ebs-csi-trust.json` | AWS 계정 ID, OIDC ID 포함 |
| `aws/eks/cluster-config.yaml` | VPC ID, Subnet ID 포함 |
| `aws/route53/` | 일회성 Route53 UPSERT 파일 |
| `aws/acm/` | 일회성 ACM DNS 검증 파일 (적용 완료) |
| `k8s/overlays/eks/monitoring/grafana-admin-secret.yaml` | Grafana 관리자 비밀번호 |
| `.env.aws` | 실제 인프라 변수 값 |

### 템플릿 파일 사용법

`.template` 파일에는 `${변수명}` 플레이스홀더가 있습니다. `.env.aws.example`을 복사해 `.env.aws`를 만들고 `envsubst`로 실제 파일을 생성합니다.

```bash
# 1. .env.aws 작성
cp .env.aws.example .env.aws
# .env.aws 파일에서 필요한 값 확인 (이미 채워져 있음)

# 2. 실제 파일 생성
source .env.aws
envsubst < aws/iam/ebs-csi-trust.json.template   > aws/iam/ebs-csi-trust.json
envsubst < aws/eks/cluster-config.yaml.template   > aws/eks/cluster-config.yaml
```

### Grafana 관리자 Secret

`kube-prometheus-stack-values.yaml`은 `admin.existingSecret: grafana-admin-secret`을 참조합니다. Helm 설치 전 Secret을 먼저 생성해야 합니다.

```bash
# example 파일 복사 후 비밀번호 설정
cp k8s/overlays/eks/monitoring/grafana-admin-secret.yaml.example \
   k8s/overlays/eks/monitoring/grafana-admin-secret.yaml

# 비밀번호 수정 후 적용
kubectl apply -f k8s/overlays/eks/monitoring/grafana-admin-secret.yaml -n monitoring
```

---

## EKS 인프라 구성

### ALB IngressGroup

두 Ingress가 `group.name: trip-service`로 단일 ALB를 공유합니다.

| Ingress | 네임스페이스 | 호스트 | 백엔드 |
|---------|------------|--------|--------|
| trip-service-ingress | trip-service-prod | 2025teamproject.store | frontend, currency, history, ranking |
| grafana-ingress | monitoring | grafana.2025teamproject.store | kube-prometheus-stack-grafana:80 |

- ACM 인증서: `*.2025teamproject.store` (SAN 포함)
- HTTP → HTTPS 강제 리다이렉트
- 백엔드 모두 `target-type: ip` (Pod 직접 라우팅)

### VPC CNI & Prefix Delegation

- `ENABLE_PREFIX_DELEGATION=true` — /28 prefix per ENI
- Launch Template v2: AL2023 NodeConfig `maxPods: 110`
- t3.medium 기준 max-pods: 17 → 110

### 스토리지

`gp3-encrypted` StorageClass (EBS CSI Driver, IRSA: `AmazonEKS_EBS_CSI_DriverRole`):

| 리소스 | 크기 | 용도 |
|--------|------|------|
| Prometheus PVC | 20Gi | 메트릭 저장 (retention: 15d) |
| Grafana PVC | 5Gi | 대시보드, 설정 |
| AlertManager PVC | 2Gi | 알림 상태 |

### 시크릿 관리

External Secrets Operator → AWS Secrets Manager 자동 동기화 (1시간 주기):

| K8s Secret | Secrets Manager 경로 |
|-----------|---------------------|
| mongodb-secret | trip-currency/prod/mongodb-secret |
| mysql-secret | trip-currency/prod/mysql-secret |
| trip-service-secrets | trip-currency/prod/trip-service-secrets |

### IAM IRSA

| 서비스 어카운트 | IAM 역할 | 정책 파일 |
|--------------|---------|---------|
| aws-load-balancer-controller | AWSLoadBalancerControllerRole | `aws/iam/alb-policy-v3.json` |
| ebs-csi-controller-sa | AmazonEKS_EBS_CSI_DriverRole | `aws/iam/ebs-csi-trust.json.template` |
| external-secrets | ExternalSecretsRole | `k8s/overlays/eks/iam-policy-external-secrets.json` |

> ALB Controller IAM 정책 v3에는 `elasticloadbalancing:SetRulePriorities`가 추가되었습니다 (IngressGroup 사용 시 필요).

---

## 모니터링 및 로깅

### kube-prometheus-stack

설치 전 Grafana admin Secret을 먼저 생성해야 합니다 ([민감 데이터 관리](#민감-데이터-관리) 참고).

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f k8s/overlays/eks/monitoring/kube-prometheus-stack-values.yaml

kubectl apply -f k8s/overlays/eks/monitoring/grafana-ingress.yaml
```

- 자동 스크래핑: `prometheus.io/scrape: "true"` 어노테이션 기준 (trip-service-prod 파드)
- Loki 데이터소스 사전 설정: `http://loki.logging.svc.cluster.local:3100` (Loki 설치 후 사용 가능)

### Fluent Bit

```bash
helm repo add fluent https://fluent.github.io/helm-charts
helm upgrade --install fluent-bit fluent/fluent-bit \
  -n logging --create-namespace \
  -f k8s/overlays/eks/logging/fluent-bit-values.yaml
```

| CloudWatch 로그 그룹 | 수집 대상 | 보존 |
|---------------------|----------|------|
| /eks/trip-service-cluster/applications | trip-service-prod 컨테이너 | 30일 |
| /eks/trip-service-cluster/infra | monitoring 네임스페이스 | 14일 |
| /eks/trip-service-cluster/host | kubelet/systemd | 14일 |

---

## 네트워크 보안

### Calico NetworkPolicy

```bash
# Calico Tigera Operator 설치
kubectl apply -f k8s/overlays/eks/calico/installation.yaml

# NetworkPolicy 전체 적용
kubectl apply -f k8s/overlays/eks/network-policies/
```

### 정책 구성 (trip-service-prod 네임스페이스)

| 파일 | 정책 |
|------|------|
| 00-default-deny.yaml | 기본 Ingress/Egress 전체 차단 |
| 01-allow-dns.yaml | 모든 Pod → CoreDNS :53 허용 |
| 02-frontend.yaml | VPC CIDR → frontend :80 |
| 03-currency.yaml | ALB → :8000; egress: Aurora/DocDB/Redis/Kafka/외부 HTTPS |
| 04-history.yaml | ALB → :8000; egress: Aurora/DocDB/Redis/Kafka |
| 05-ranking.yaml | ALB → :8000; egress: DocDB/Redis/Kafka |
| 06-dataingestor.yaml | ingress 없음; egress: Kafka/외부 HTTPS |
| 07-kafka.yaml | 내부 서비스 → :9092; egress: Zookeeper :2181 |
| 08-kafka-ui.yaml | ingress 완전 차단; egress: Kafka/Zookeeper |
| 09-zookeeper.yaml | kafka/kafka-ui → :2181만 허용 |
| 10-allow-prometheus-scrape.yaml | monitoring ns → 모든 Pod :8000/:80 |

---

## 공급망 보안 (SBOM)

### ECR Enhanced Scanning

전체 ECR 레포지토리에 AWS Inspector v2 기반 스캔 활성화:

```bash
aws ecr put-registry-scanning-configuration \
  --scan-type ENHANCED \
  --rules '[{"repositoryFilters":[{"filter":"*","filterType":"WILDCARD"}],"scanFrequency":"CONTINUOUS_SCAN"}]' \
  --region ap-northeast-2
```

| 항목 | 값 |
|------|-----|
| 스캔 유형 | ENHANCED (AWS Inspector v2) |
| 스캔 빈도 | CONTINUOUS_SCAN (Push 시 + 신규 CVE 발표 시 자동 재스캔) |
| 대상 레포지토리 | 전체 (`*`) |

### CI/CD 파이프라인 SBOM 스테이지

`Jenkinsfile.production`의 `Docker Build & Push` 완료 후 실행:

```
Docker Build & Push (ECR)
  → SBOM & Vulnerability Scan  ← 5개 서비스 병렬
       ├─ trivy image --format cyclonedx  → sbom-{서비스}.json (Jenkins 아티팩트 보관)
       └─ trivy image --exit-code 1 --severity CRITICAL --ignore-unfixed
  → Update GitOps Repository
```

| 단계 | 도구 | 동작 |
|------|------|------|
| SBOM 생성 | Trivy | CycloneDX JSON 포맷, 서비스별 파일 생성 |
| 취약점 스캔 | Trivy | CRITICAL + 패치 버전 존재 시 파이프라인 중단 |

> SBOM 파일(`sbom-*.json`)은 Jenkins 아티팩트로 빌드별 보관됩니다.

---

## 배포 가이드

### 사전 요구사항

```bash
aws eks update-kubeconfig --name trip-service-cluster --region ap-northeast-2
kubectl cluster-info
kubectl get nodes
```

### EKS 환경 전체 적용 순서

```bash
# 1. 민감 파일 생성 (최초 1회)
source .env.aws
envsubst < aws/iam/ebs-csi-trust.json.template > aws/iam/ebs-csi-trust.json
envsubst < aws/eks/cluster-config.yaml.template > aws/eks/cluster-config.yaml

# 2. Namespace 및 기본 리소스
kubectl apply -k k8s/overlays/eks

# 3. Calico 설치 및 NetworkPolicy 적용
kubectl apply -f k8s/overlays/eks/calico/installation.yaml
kubectl apply -f k8s/overlays/eks/network-policies/

# 4. Grafana admin Secret 생성
cp k8s/overlays/eks/monitoring/grafana-admin-secret.yaml.example \
   k8s/overlays/eks/monitoring/grafana-admin-secret.yaml
# 비밀번호 수정 후:
kubectl apply -f k8s/overlays/eks/monitoring/grafana-admin-secret.yaml -n monitoring

# 5. Prometheus + Grafana 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f k8s/overlays/eks/monitoring/kube-prometheus-stack-values.yaml
kubectl apply -f k8s/overlays/eks/monitoring/grafana-ingress.yaml

# 6. Fluent Bit 설치
helm repo add fluent https://fluent.github.io/helm-charts
helm upgrade --install fluent-bit fluent/fluent-bit \
  -n logging --create-namespace \
  -f k8s/overlays/eks/logging/fluent-bit-values.yaml
```

### 배포 상태 확인

```bash
# 전체 파드 상태
kubectl get pods -A

# Ingress 상태 (ALB 주소 확인)
kubectl get ingress -A

# NetworkPolicy 확인
kubectl get networkpolicy -n trip-service-prod

# HPA 상태
kubectl get hpa -n trip-service-prod

# PVC 상태
kubectl get pvc -n monitoring
```

### 서비스 테스트

```bash
curl https://2025teamproject.store/health
curl https://2025teamproject.store/api/v1/currencies
curl https://grafana.2025teamproject.store/api/health
```

---

## 잔여 보안 조치

현재 운영 중이나 미조치 항목입니다. 상세 내용은 `README.md` 참고.

| 항목 | 우선순위 | 설명 |
|------|---------|------|
| EKS API 서버 CIDR 제한 | HIGH | `publicAccessCidrs` 0.0.0.0/0 → 운영 IP로 제한 |
| Prometheus Adapter 설치 | MEDIUM | HPA custom metrics 공급 완성 |
| Pod securityContext 설정 | MEDIUM | 전 Deployment `runAsNonRoot: true` 적용 |
| kafka-ui Basic Auth | MEDIUM | NetworkPolicy ingress 차단됨, UI 자체 인증 미적용 |
| Redis AUTH + TLS 활성화 | MEDIUM | ElastiCache 재생성 필요 (in-place 변경 불가) |
| frontend-config API URL 수정 | MEDIUM | dev URL → `https://2025teamproject.store` |
