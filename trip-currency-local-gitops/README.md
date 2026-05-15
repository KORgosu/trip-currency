# Trip Currency Service - GitOps Repository

여행 환율 서비스 플랫폼의 Kubernetes 매니페스트 및 AWS 인프라 설정을 관리하는 저장소입니다.

---

## 목차

- [개요](#개요)
- [현재 운영 환경](#현재-운영-환경)
- [디렉토리 구조](#디렉토리-구조)
- [민감 데이터 관리](#민감-데이터-관리)
- [EKS 인프라 구성](#eks-인프라-구성)
- [보안 적용 현황](#보안-적용-현황)
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
              │  │                             PSA: enforce=restricted  │
              │  │  service-frontend  (ClusterIP :8080)                │
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
├── .env.aws.example                       # AWS 인프라 변수 예시
│
├── k8s/
│   ├── base/                              # 공통 매니페스트
│   │   ├── kustomization.yaml
│   │   ├── configmap.yaml                 # 공통 ConfigMap
│   │   ├── secrets.yaml                   # 로컬 환경용 Secret (EKS는 ESO 사용)
│   │   ├── ingress.yaml                   # NGINX Ingress 규칙 (로컬 K8s용)
│   │   ├── kafka/
│   │   │   ├── serviceaccounts.yaml       # sa-kafka, sa-zookeeper, sa-kafka-ui, sa-kafka-exporter
│   │   │   ├── kafka.yaml                 # Deployment + Service
│   │   │   ├── zookeeper.yaml             # Deployment + Service
│   │   │   ├── kafka-ui.yaml              # Deployment + Service
│   │   │   ├── kafka-exporter.yaml        # Deployment + Service (v1.7.0, PSA restricted, :9308)
│   │   │   └── kustomization.yaml
│   │   ├── redis/                         # 로컬 환경용 (EKS는 ElastiCache 사용)
│   │   ├── mysql/                         # 로컬 환경용 (EKS는 Aurora 사용)
│   │   ├── mongodb/                       # 로컬 환경용 (EKS는 DocumentDB 사용)
│   │   ├── metallb/                       # IPAddressPool (로컬 K8s용)
│   │   ├── ingress-controller/            # NGINX Controller + RBAC (로컬 K8s용)
│   │   └── services/
│   │       ├── currency-service/
│   │       │   ├── serviceaccount.yaml    # sa-currency (automountToken: false)
│   │       │   ├── deployment.yaml
│   │       │   ├── service.yaml
│   │       │   ├── hpa.yaml
│   │       │   └── kustomization.yaml
│   │       ├── history-service/
│   │       │   ├── serviceaccount.yaml    # sa-history (automountToken: false)
│   │       │   ├── deployment.yaml
│   │       │   ├── service.yaml
│   │       │   ├── hpa.yaml
│   │       │   └── kustomization.yaml
│   │       ├── ranking-service/
│   │       │   ├── serviceaccount.yaml    # sa-ranking (automountToken: false)
│   │       │   ├── deployment.yaml
│   │       │   ├── service.yaml
│   │       │   ├── hpa.yaml
│   │       │   └── kustomization.yaml
│   │       ├── dataingestor-service/
│   │       │   ├── serviceaccount.yaml    # sa-dataingestor (automountToken: false)
│   │       │   ├── cronjob.yaml
│   │       │   └── kustomization.yaml
│   │       └── frontend/
│   │           ├── serviceaccount.yaml    # sa-frontend (automountToken: false)
│   │           ├── deployment.yaml        # nginx-unprivileged:alpine, uid 101, :8080
│   │           ├── service.yaml           # port 80 → targetPort 8080
│   │           ├── hpa.yaml
│   │           ├── configmap.yaml         # api-base-url: https://2025teamproject.store
│   │           ├── ingress.yaml           # NGINX Ingress (로컬 K8s용)
│   │           └── kustomization.yaml
│   │
│   └── overlays/
│       ├── dev/                           # 로컬 개발 환경 (NGINX Ingress)
│       ├── staging/
│       ├── prod/                          # 로컬 프로덕션 (NGINX Ingress)
│       └── eks/                           # AWS EKS 프로덕션 환경
│           ├── kustomization.yaml         # ECR 이미지 패치, AWS ConfigMap 패치
│           ├── namespace.yaml             # PSA enforce=restricted 레이블 포함
│           ├── ingress.yaml               # ALB Ingress (trip-service-prod)
│           ├── storageclass.yaml          # gp3-encrypted StorageClass
│           ├── iam-policy-external-secrets.json
│           ├── calico/
│           │   └── installation.yaml      # Calico Tigera Operator (AmazonVPC mode)
│           ├── external-secrets/
│           │   ├── cluster-secret-store.yaml
│           │   ├── external-secret.yaml
│           │   └── kustomization.yaml
│           ├── monitoring/
│           │   ├── kube-prometheus-stack-values.yaml  # Grafana sidecar, AlertManager Slack
│           │   ├── grafana-ingress.yaml
│           │   ├── grafana-admin-secret.yaml.example
│           │   ├── alertmanager-externalsecret.yaml   # ESO → Slack webhook URL
│           │   ├── prometheus-rules-stability.yaml    # 서비스 안정성 알림 8개
│           │   ├── prometheus-rules-security.yaml     # 보안 이상 알림 4개
│           │   ├── prometheus-rules-kafka.yaml        # Kafka Consumer Lag 알림 4개
│           │   └── dashboards/
│           │       ├── service-stability-dashboard.yaml  # Grafana 대시보드 ConfigMap
│           │       ├── security-dashboard.yaml
│           │       └── kafka-dashboard.yaml
│           ├── logging/
│           │   └── fluent-bit-values.yaml
│           └── network-policies/
│               ├── 00-default-deny.yaml
│               ├── 01-allow-dns.yaml
│               ├── 02-frontend.yaml       # VPC CIDR → :8080
│               ├── 03-currency.yaml
│               ├── 04-history.yaml
│               ├── 05-ranking.yaml
│               ├── 06-dataingestor.yaml
│               ├── 07-kafka.yaml          # kafka-exporter ingress 추가
│               ├── 08-kafka-ui.yaml
│               ├── 09-zookeeper.yaml
│               ├── 10-allow-prometheus-scrape.yaml  # monitoring ns → :8000/:8080/:9308
│               └── 11-kafka-exporter.yaml           # monitoring→:9308, egress kafka:9092
│
├── aws/                                   # AWS CLI 입력 파일
│   ├── eks/
│   │   ├── cluster-config.yaml.template   # eksctl ClusterConfig (플레이스홀더)
│   │   ├── logging-config.json            # 컨트롤 플레인 로깅 활성화 설정
│   │   └── lt-userdata.json               # Launch Template v2 user data (maxPods:110)
│   ├── iam/
│   │   ├── alb-policy-v2.json
│   │   ├── alb-policy-v3.json             # 현재 적용 (SetRulePriorities 포함)
│   │   └── ebs-csi-trust.json.template    # IRSA 신뢰 정책 (플레이스홀더)
│   ├── route53/                           # .gitignore — 일회성 파일
│   │   ├── main-domain.json
│   │   └── grafana-domain.json
│   └── acm/                               # .gitignore — DNS 검증 완료
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
cp .env.aws.example .env.aws
# .env.aws 파일에서 필요한 값 확인

source .env.aws
envsubst < aws/iam/ebs-csi-trust.json.template   > aws/iam/ebs-csi-trust.json
envsubst < aws/eks/cluster-config.yaml.template   > aws/eks/cluster-config.yaml
```

### Grafana 관리자 Secret

`kube-prometheus-stack-values.yaml`은 `admin.existingSecret: grafana-admin-secret`을 참조합니다. Helm 설치 전 Secret을 먼저 생성해야 합니다.

```bash
cp k8s/overlays/eks/monitoring/grafana-admin-secret.yaml.example \
   k8s/overlays/eks/monitoring/grafana-admin-secret.yaml

kubectl apply -f k8s/overlays/eks/monitoring/grafana-admin-secret.yaml -n monitoring
```

---

## EKS 인프라 구성

### ALB IngressGroup

두 Ingress가 `group.name: trip-service`로 단일 ALB를 공유합니다.

| Ingress | 네임스페이스 | 호스트 | 백엔드 |
|---------|------------|--------|--------|
| trip-service-ingress | trip-service-prod | 2025teamproject.store | frontend(:80), currency, history, ranking |
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
| alertmanager-slack-webhook | trip-currency/prod/alertmanager-slack (key: slack-webhook-url) |

### IAM IRSA

| 서비스 어카운트 | IAM 역할 | 정책 파일 |
|--------------|---------|---------|
| aws-load-balancer-controller | AWSLoadBalancerControllerRole | `aws/iam/alb-policy-v3.json` |
| ebs-csi-controller-sa | AmazonEKS_EBS_CSI_DriverRole | `aws/iam/ebs-csi-trust.json.template` |
| external-secrets | ExternalSecretsRole | `k8s/overlays/eks/iam-policy-external-secrets.json` |

> ALB Controller IAM 정책 v3에는 `elasticloadbalancing:SetRulePriorities`가 추가되었습니다 (IngressGroup 사용 시 필요).

---

## 보안 적용 현황

### Pod Security Admission (PSA)

`namespace.yaml`에 `enforce=restricted` 레이블 적용 — 기준 미달 Pod는 API 서버에서 즉시 거부됩니다.

```yaml
# k8s/overlays/eks/namespace.yaml
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/warn: restricted
```

### 컨테이너 보안 (securityContext)

| 서비스 | 이미지 | runAsNonRoot | readOnlyRootFilesystem | seccompProfile |
|--------|--------|-------------|----------------------|---------------|
| frontend | nginx-unprivileged:alpine | ✅ uid 101 | ✅ | RuntimeDefault |
| currency | ECR | ✅ uid 1000 | ✅ | RuntimeDefault |
| history | ECR | ✅ uid 1000 | ✅ | RuntimeDefault |
| ranking | ECR | ✅ uid 1000 | ✅ | RuntimeDefault |
| dataingestor | ECR | ✅ uid 1000 | ✅ | RuntimeDefault |
| kafka | cp-kafka:7.4.0 | ✅ uid 1000 | - | RuntimeDefault |
| zookeeper | cp-zookeeper:7.4.0 | ✅ uid 1000 | - | RuntimeDefault |
| kafka-ui | kafka-ui:latest | ✅ uid 1000 | - | RuntimeDefault |

> frontend는 `nginx:alpine`(root 필수, :80) 대신 `nginxinc/nginx-unprivileged:alpine`(uid 101, :8080)을 사용합니다.

### Kubernetes RBAC (인-클러스터)

전용 ServiceAccount를 서비스별로 분리하고 K8s API 토큰 마운트를 비활성화합니다.

| ServiceAccount | 대상 | automountServiceAccountToken |
|---------------|------|------------------------------|
| sa-frontend | service-frontend | false |
| sa-currency | service-currency | false |
| sa-history | service-history | false |
| sa-ranking | service-ranking | false |
| sa-dataingestor | service-dataingestor | false |
| sa-kafka | kafka | false |
| sa-zookeeper | zookeeper | false |
| sa-kafka-ui | kafka-ui | false |
| sa-kafka-exporter | kafka-exporter | false |

> 인프라 컴포넌트(ALB Controller, ESO, EBS CSI)는 IRSA로 별도 관리됩니다.

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

- 자동 스크래핑: `prometheus.io/scrape: "true"` 어노테이션 기준 (trip-service-prod 파드, 포트 8000·8080·9308)

### AlertManager Slack 연동

AlertManager가 Slack으로 알림을 보내려면 AWS Secrets Manager에 webhook URL이 저장되어 있어야 합니다.

```bash
# 1. Secrets Manager에 webhook URL 저장 (최초 1회)
aws secretsmanager create-secret \
  --name trip-currency/prod/alertmanager-slack \
  --secret-string '{"slack-webhook-url":"https://hooks.slack.com/services/XXXX/YYYY/ZZZZ"}' \
  --region ap-northeast-2

# 2. ESO ExternalSecret 적용 (alertmanager-slack-webhook Secret 자동 생성)
kubectl apply -f k8s/overlays/eks/monitoring/alertmanager-externalsecret.yaml -n monitoring

# 3. Secret 생성 확인 후 Helm 업그레이드
kubectl get secret alertmanager-slack-webhook -n monitoring
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f k8s/overlays/eks/monitoring/kube-prometheus-stack-values.yaml
```

알림 채널:
- `severity: critical` → `#alerts-critical`
- `severity: warning` → `#alerts-warning`

### PrometheusRule (알림 규칙)

```bash
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-stability.yaml
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-security.yaml
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-kafka.yaml

# 적용 확인
kubectl get prometheusrule -n monitoring
```

| 파일 | 알림 수 | 주요 알림 |
|------|--------|---------|
| prometheus-rules-stability.yaml | 8개 | PodCrashLooping, PodNotReady, DeploymentReplicasMismatch, HPAMaxReplicas, NodeHighCPU/Memory/Disk, PVCUsageHigh |
| prometheus-rules-security.yaml | 4개 | AbnormalPodRestartSpike, ContainerCPUThrottling, HighNetworkEgress, UnexpectedPrivilegedContainer |
| prometheus-rules-kafka.yaml | 4개 | KafkaConsumerGroupLagHigh(>1000), KafkaConsumerGroupLagCritical(>5000), KafkaBrokerDown, KafkaConsumerGroupNoProgress |

### Grafana 대시보드

대시보드는 `grafana_dashboard: "1"` 레이블이 붙은 ConfigMap을 Grafana sidecar가 자동 임포트합니다.

```bash
kubectl apply -f k8s/overlays/eks/monitoring/dashboards/service-stability-dashboard.yaml
kubectl apply -f k8s/overlays/eks/monitoring/dashboards/security-dashboard.yaml
kubectl apply -f k8s/overlays/eks/monitoring/dashboards/kafka-dashboard.yaml
```

| ConfigMap | Grafana UID | 설명 |
|-----------|------------|------|
| grafana-dashboard-service-stability | trip-stability | Pod 안정성·Node 리소스·HPA 시각화 |
| grafana-dashboard-security | trip-security | 비정상 재시작·네트워크 이상·CPU 스로틀 |
| grafana-dashboard-kafka | trip-kafka | Consumer Lag·오프셋·Broker 상태 |

> kube-prometheus-stack Helm values에 `grafana.sidecar.dashboards.enabled: true`가 설정되어 있어 ConfigMap 적용 즉시 자동 반영됩니다.

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
kubectl apply -f k8s/overlays/eks/calico/installation.yaml
kubectl apply -f k8s/overlays/eks/network-policies/
```

### 정책 구성 (trip-service-prod 네임스페이스)

| 파일 | 정책 |
|------|------|
| 00-default-deny.yaml | 기본 Ingress/Egress 전체 차단 |
| 01-allow-dns.yaml | 모든 Pod → CoreDNS :53 허용 |
| 02-frontend.yaml | VPC CIDR → frontend :8080 |
| 03-currency.yaml | ALB → :8000; egress: Aurora/DocDB/Redis/Kafka/외부 HTTPS |
| 04-history.yaml | ALB → :8000; egress: Aurora/DocDB/Redis/Kafka |
| 05-ranking.yaml | ALB → :8000; egress: DocDB/Redis/Kafka |
| 06-dataingestor.yaml | ingress 없음; egress: Kafka/외부 HTTPS |
| 07-kafka.yaml | 내부 서비스 + kafka-exporter → :9092; egress: Zookeeper :2181 |
| 08-kafka-ui.yaml | ingress 완전 차단; egress: Kafka/Zookeeper |
| 09-zookeeper.yaml | kafka/kafka-ui → :2181만 허용 |
| 10-allow-prometheus-scrape.yaml | monitoring ns → 모든 Pod :8000/:8080/:9308 |
| 11-kafka-exporter.yaml | monitoring ns → :9308; egress: kafka :9092 |

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

# 2. Namespace 및 기본 리소스 (PSA 레이블 포함)
kubectl apply -k k8s/overlays/eks

# 3. Calico 설치 및 NetworkPolicy 적용
kubectl apply -f k8s/overlays/eks/calico/installation.yaml
kubectl apply -f k8s/overlays/eks/network-policies/

# 4. Grafana admin Secret 생성
cp k8s/overlays/eks/monitoring/grafana-admin-secret.yaml.example \
   k8s/overlays/eks/monitoring/grafana-admin-secret.yaml
# 비밀번호 수정 후:
kubectl apply -f k8s/overlays/eks/monitoring/grafana-admin-secret.yaml -n monitoring

# 5. AlertManager Slack webhook Secret 생성 (ESO 사용)
#    - AWS Secrets Manager에 trip-currency/prod/alertmanager-slack 저장 후:
kubectl apply -f k8s/overlays/eks/monitoring/alertmanager-externalsecret.yaml -n monitoring

# 6. Prometheus + Grafana 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f k8s/overlays/eks/monitoring/kube-prometheus-stack-values.yaml
kubectl apply -f k8s/overlays/eks/monitoring/grafana-ingress.yaml

# 7. PrometheusRule + Grafana 대시보드 적용
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-stability.yaml
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-security.yaml
kubectl apply -f k8s/overlays/eks/monitoring/prometheus-rules-kafka.yaml
kubectl apply -f k8s/overlays/eks/monitoring/dashboards/

# 8. Fluent Bit 설치
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

# ServiceAccount 확인
kubectl get serviceaccount -n trip-service-prod

# PSA 레이블 확인
kubectl get namespace trip-service-prod --show-labels

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

현재 운영 중이나 미조치 항목입니다. 상세 내용은 루트 `README.md` 참고.

| 항목 | 우선순위 | 설명 |
|------|---------|------|
| Prometheus Adapter 설치 | MEDIUM | HPA custom metrics 공급 완성 필요 |
| kafka-ui Basic Auth | MEDIUM | NetworkPolicy로 ingress 차단됨, UI 자체 인증 미적용 |
| Redis AUTH + TLS 활성화 | MEDIUM | ElastiCache 재생성 필요 (in-place 변경 불가) |
| latest 태그 고정 | MEDIUM | kafka-ui 등 외부 이미지 버전 고정 필요 |
| Kafka StatefulSet + PVC | MEDIUM | 단일 레플리카 + PVC 없음 → 재시작 시 메시지 유실 |
