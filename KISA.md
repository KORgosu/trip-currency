# 클라우드 네이티브 환경의 다층 보안 아키텍처 구현 사례
## Trip Currency Service — AWS EKS 기반 마이크로서비스 보안 설계

> 발표 대상: KISA (한국인터넷진흥원)
> 클러스터: `trip-service-cluster` | 리전: `ap-northeast-2` (서울) | Kubernetes v1.33

---

## 목차

1. [서비스 개요](#1-서비스-개요)
2. [클라우드 인프라 구성](#2-클라우드-인프라-구성)
3. [위협 모델 및 보안 설계 원칙](#3-위협-모델-및-보안-설계-원칙)
4. [보안 전략 적용 순서](#4-보안-전략-적용-순서)
5. [계층별 보안 전략 상세](#5-계층별-보안-전략-상세)
6. [CI/CD 파이프라인 보안](#6-cicd-파이프라인-보안)
7. [관측성 및 위협 탐지](#7-관측성-및-위협-탐지)
8. [보안 점검 결과 요약](#8-보안-점검-결과-요약)
9. [잔여 과제 및 개선 계획](#9-잔여-과제-및-개선-계획)

---

## 1. 서비스 개요

### 1-1. 서비스 소개

**Trip Currency Service**는 여행자를 위한 실시간 환율 정보 제공 플랫폼입니다.

| 항목 | 내용 |
|------|------|
| 서비스명 | Trip Currency Service |
| 도메인 | `https://2025teamproject.store` |
| 아키텍처 | 마이크로서비스 (MSA) |
| 배포 환경 | AWS EKS (Kubernetes v1.33) |
| 데이터 수집 | ExchangeRate-API v6 (70개 통화, 5분 주기) |

### 1-2. 마이크로서비스 구성

```
┌─────────────────────────────────────────────────────┐
│                   서비스 레이어                       │
│                                                     │
│  service-frontend   ← React + Vite (nginx:8080)    │
│  service-currency   ← FastAPI + Redis 캐시          │
│  service-history    ← FastAPI + Aurora MySQL        │
│  service-ranking    ← FastAPI + DocumentDB          │
│  service-dataingestor ← CronJob (5분 주기 수집)     │
│                                                     │
├─────────────────────────────────────────────────────┤
│                   메시지 레이어                       │
│  Kafka + Zookeeper + kafka-ui + kafka-exporter      │
└─────────────────────────────────────────────────────┘
```

---

## 2. 클라우드 인프라 구성

### 2-1. 전체 아키텍처

```
인터넷
  ├─ Route53: 2025teamproject.store         (A Alias)
  └─ Route53: grafana.2025teamproject.store (A Alias)
                  │
    ┌─────────────▼──────────────────────────────────────────┐
    │ ALB: trip-service-alb (internet-facing)                 │
    │ HTTP:80 → HTTPS:443 강제 리다이렉트                      │
    │ ACM 인증서: *.2025teamproject.store (자동 갱신)           │
    └─────────────┬──────────────────────────────────────────┘
                  │ HTTPS:443
    ┌─────────────▼──────────────────────────────────────────┐
    │ VPC: 192.168.0.0/16  (ap-northeast-2)                   │
    │                                                         │
    │  ┌──────────── EKS: trip-service-cluster ─────────────┐ │
    │  │ 노드: t3.medium × 3 (AL2023, Kubernetes v1.33)     │ │
    │  │                                                     │ │
    │  │  [trip-service-prod] ── NetworkPolicy: 적용됨        │ │
    │  │  frontend(3) · currency(3) · history(2) · ranking(2)│ │
    │  │  kafka · zookeeper · kafka-ui · kafka-exporter      │ │
    │  │  dataingestor (CronJob, 5분 주기)                   │ │
    │  │                                                     │ │
    │  │  [monitoring]                                       │ │
    │  │  Prometheus · Grafana · AlertManager · node-exporter│ │
    │  │                                                     │ │
    │  │  [logging]                                          │ │
    │  │  Fluent Bit (DaemonSet × 3) → CloudWatch           │ │
    │  │                                                     │ │
    │  │  [kube-system]                                      │ │
    │  │  ALB Controller · ESO · CoreDNS · Calico · EBS CSI │ │
    │  └─────────────────────────────────────────────────────┘ │
    │                                                         │
    │  Aurora MySQL ─┐                                        │
    │  DocumentDB   ─┼─ VPC-only 접근 (192.168.0.0/16)       │
    │  ElastiCache  ─┘                                        │
    │                                                         │
    │  CloudWatch Logs / Secrets Manager / GuardDuty / ECR   │
    └─────────────────────────────────────────────────────────┘
```

### 2-2. 노드 구성

| 항목 | 값 |
|------|-----|
| 클러스터명 | trip-service-cluster |
| 노드 그룹 | trip-service-workers |
| 인스턴스 | t3.medium × 3 (min:2 / max:5) |
| OS | Amazon Linux 2023 (nodeadm) |
| 컨테이너 런타임 | containerd 2.2.3 |
| max-pods | 110 (VPC Prefix Delegation) |
| 인증 모드 | API_AND_CONFIG_MAP |

### 2-3. 데이터베이스 계층

| DB | 엔진 | 포트 | 접근 통제 |
|----|------|------|----------|
| Aurora MySQL | MySQL 8.0 호환 | 3306 | VPC SG + NetworkPolicy |
| DocumentDB | MongoDB 5.0 호환 | 27017 | VPC SG + NetworkPolicy |
| ElastiCache | Redis 7 | 6379 | VPC SG + NetworkPolicy |

---

## 3. 위협 모델 및 보안 설계 원칙

### 3-1. 주요 위협 시나리오

| # | 위협 | 공격 경로 | 대응 전략 |
|---|------|----------|----------|
| T1 | 외부 침입 | 인터넷 → 서비스 직접 접근 | ALB 단일 진입점, HTTPS 전용 |
| T2 | 컨테이너 탈출 | Pod 취약점 → 호스트 권한 획득 | securityContext, PSA restricted |
| T3 | Lateral Movement | 침해 Pod → 내부 서비스 횡이동 | NetworkPolicy default-deny |
| T4 | 자격증명 탈취 | 코드/환경변수 → 비밀번호 노출 | ESO + Secrets Manager, IRSA |
| T5 | 공급망 공격 | 악성 이미지 → 프로덕션 배포 | Trivy SBOM, ECR Enhanced Scanning |
| T6 | 내부자 위협 | K8s API 남용 → 클러스터 장악 | RBAC, API 서버 CIDR 제한 |
| T7 | 데이터 유출 | DB 직접 접근 → 데이터 탈취 | VPC 격리, NetworkPolicy, TLS |
| T8 | 지속성 확보 | 악성 바이너리 → 파일시스템 기록 | readOnlyRootFilesystem |

### 3-2. 보안 설계 원칙

- **최소 권한 (Least Privilege)**: 각 구성 요소는 업무에 필요한 최소한의 권한만 보유
- **심층 방어 (Defense in Depth)**: 네트워크·컨테이너·데이터·감사 4개 계층 중첩 방어
- **제로 트러스트 (Zero Trust)**: 기본 차단 후 명시적 허용 (default-deny NetworkPolicy)
- **불변 인프라 (Immutable Infrastructure)**: readOnlyRootFilesystem, GitOps 기반 배포
- **가시성 확보 (Observability)**: 모든 계층에서 로그·메트릭·알림 수집

---

## 4. 보안 전략 적용 순서

보안 조치는 **인프라 기반 → 네트워크 격리 → 컨테이너 보안 → 비밀 관리 → 감사·탐지** 순서로 계층적으로 적용했습니다.

```
Phase 1. 인프라 기반 보안
  │  ├─ EKS API 서버 CIDR 제한 (0.0.0.0/0 → 222.109.238.0/24)
  │  ├─ EKS 컨트롤 플레인 로깅 전체 활성화
  │  ├─ VPC 격리 DB 배포 (Aurora / DocDB / ElastiCache)
  │  └─ EBS 암호화 StorageClass (gp3-encrypted, KMS)
  │
Phase 2. 네트워크 계층 보안
  │  ├─ Calico 설치 (AmazonVPC 모드, policy-engine-only)
  │  ├─ default-deny NetworkPolicy 적용
  │  ├─ 서비스별 최소 권한 NetworkPolicy 12개 작성
  │  ├─ ALB 단일 진입점 구성 (HTTP→HTTPS 강제 리다이렉트)
  │  └─ NLB 제거 (HTTP 평문 우회 경로 차단)
  │
Phase 3. 컨테이너 계층 보안
  │  ├─ securityContext 적용 (runAsNonRoot, capabilities.drop:ALL)
  │  ├─ readOnlyRootFilesystem 적용 (전 서비스)
  │  ├─ seccompProfile: RuntimeDefault 적용 (전 워크로드)
  │  ├─ nginx-unprivileged 전환 (frontend root 실행 제거)
  │  └─ PSA enforce:restricted 네임스페이스 레이블 적용
  │
Phase 4. 접근 제어 (RBAC / IRSA)
  │  ├─ 서비스별 전용 ServiceAccount 생성 (9개)
  │  ├─ automountServiceAccountToken: false 전 워크로드 적용
  │  └─ IRSA 구성 (ALB Controller / ESO / EBS CSI)
  │
Phase 5. 비밀 관리
  │  ├─ External Secrets Operator 설치
  │  ├─ AWS Secrets Manager 연동 (3개 Secret, 1시간 갱신)
  │  └─ GitOps 저장소 민감 정보 제거 (.gitignore + 템플릿화)
  │
Phase 6. 위협 탐지 및 감사
  │  ├─ GuardDuty 활성화 (8개 탐지 기능 전체)
  │  ├─ Fluent Bit → CloudWatch Logs (3개 로그 그룹)
  │  ├─ kube-prometheus-stack 배포 (Prometheus + Grafana + AlertManager)
  │  ├─ Grafana 대시보드 3종 (Stability / Security / Kafka)
  │  └─ AlertManager Slack 알림 연동
  │
Phase 7. 공급망 보안
     ├─ ECR Enhanced Scanning (AWS Inspector v2, CONTINUOUS_SCAN)
     └─ Jenkins 파이프라인 Trivy SBOM + CRITICAL 취약점 차단
```

---

## 5. 계층별 보안 전략 상세

### 5-1. 네트워크 격리 (NetworkPolicy)

#### 적용 방법

Calico Tigera Operator v3.29.1을 AmazonVPC 모드(policy-engine-only)로 설치합니다. 기존 VPC CNI(aws-node)는 유지하고 Calico는 NetworkPolicy 엔진으로만 동작합니다.

```bash
# Calico 설치
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.1/manifests/tigera-operator.yaml
kubectl apply -f k8s/overlays/eks/calico/installation.yaml
```

```yaml
# installation.yaml — AmazonVPC 모드, policy-engine-only
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  cni:
    type: AmazonVPC
  networkPolicy:
    type: Calico
```

#### NetworkPolicy 구성 (12개)

| 정책 파일 | 대상 | 방향 | 허용 내용 |
|----------|------|------|---------|
| `00-default-deny.yaml` | 전체 Pod | Ingress+Egress | **전체 차단** (기본값) |
| `01-allow-dns.yaml` | 전체 Pod | Egress | CoreDNS :53 (UDP/TCP) |
| `02-frontend.yaml` | service-frontend | Ingress | VPC CIDR → :8080 |
| `03-currency.yaml` | service-currency | Ingress+Egress | ALB→:8000 / Aurora·Redis·Kafka·HTTPS |
| `04-history.yaml` | service-history | Ingress+Egress | ALB→:8000 / Aurora·DocDB·Redis·Kafka |
| `05-ranking.yaml` | service-ranking | Ingress+Egress | ALB→:8000 / DocDB·Redis·Kafka |
| `06-dataingestor.yaml` | service-dataingestor | Egress only | Kafka·Aurora·DocDB·Redis·외부 HTTPS |
| `07-kafka.yaml` | kafka | Ingress+Egress | 내부서비스→:9092 / Zookeeper:2181 / inter-broker:9093 |
| `08-kafka-ui.yaml` | kafka-ui | Ingress 완전차단 | Egress: Kafka·Zookeeper만 허용 |
| `09-zookeeper.yaml` | zookeeper | Ingress | kafka·kafka-ui→:2181 |
| `10-allow-prometheus-scrape.yaml` | 전체 Pod | Ingress | monitoring ns → :8000/:8080/:9308 |
| `11-kafka-exporter.yaml` | kafka-exporter | Ingress+Egress | monitoring ns→:9308 / kafka:9092 |

#### 기대 효과

| 위협 | 대응 |
|------|------|
| Lateral Movement | 침해 Pod에서 인접 서비스로 TCP 연결 자체 불가 |
| C&C 통신 | dataingestor egress 화이트리스트 외 외부 연결 차단 |
| DB 무단 접근 | currency·history·ranking만 DB egress 허용, 나머지 물리적 차단 |
| Blast Radius | 하나의 Pod 침해가 허용 목록 외 전파 불가 |

---

### 5-2. 외부 접근 단일화 (ALB + HTTPS)

#### 적용 방법

```yaml
# ingress.yaml — ALB IngressGroup, HTTP→HTTPS 강제 리다이렉트
annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
  alb.ingress.kubernetes.io/ssl-redirect: '443'
  alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
  alb.ingress.kubernetes.io/group.name: trip-service
```

```bash
# service-frontend LoadBalancer → ClusterIP 전환 (NLB 제거)
# HTTP 평문 우회 경로 완전 차단
```

#### 기대 효과

- MITM 공격 방지: 전 구간 TLS 암호화
- 공격 표면 최소화: 외부 진입점 ALB 단일 경로로 통일
- 인증서 자동 갱신: ACM 관리로 만료 위험 제거

---

### 5-3. EKS API 서버 접근 제한

#### 적용 방법

```bash
aws eks update-cluster-config \
  --name trip-service-cluster \
  --resources-vpc-config \
    endpointPublicAccess=true,\
    endpointPrivateAccess=true,\
    publicAccessCidrs="222.109.238.0/24"
```

#### 기대 효과

- 허용 CIDR 외부에서 API 서버 TCP 연결 자체 불가
- 자격증명 탈취 시나리오 무력화 (토큰이 유출되어도 외부에서 접근 불가)
- 무차별 대입 원천 차단

---

### 5-4. 컨테이너 보안 (securityContext + PSA)

#### 적용 방법

모든 Deployment / CronJob에 Pod 및 컨테이너 수준 securityContext 적용:

```yaml
# Pod 수준
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault      # PSA restricted 필수 요건

# 컨테이너 수준
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]
```

```yaml
# namespace.yaml — PSA enforce:restricted 적용
labels:
  pod-security.kubernetes.io/enforce: restricted
  pod-security.kubernetes.io/audit: restricted
  pod-security.kubernetes.io/warn: restricted
```

**frontend 특이 사항**: `nginx:alpine`은 root(uid 0) 필수이며 포트 80 바인딩에 `NET_BIND_SERVICE` capability 필요 → `nginxinc/nginx-unprivileged:alpine`(uid 101, :8080)으로 교체하여 PSA restricted 완전 준수.

#### 서비스별 적용 현황

| 서비스 | runAsUser | readOnlyRootFilesystem | capabilities | seccompProfile |
|--------|-----------|----------------------|--------------|---------------|
| frontend | 101 (nginx) | ✅ | ALL drop | RuntimeDefault |
| currency | 1000 | ✅ | ALL drop | RuntimeDefault |
| history | 1000 | ✅ | ALL drop | RuntimeDefault |
| ranking | 1000 | ✅ | ALL drop | RuntimeDefault |
| dataingestor | 1000 | ✅ | ALL drop | RuntimeDefault |
| kafka | 1000 | - | ALL drop | RuntimeDefault |
| zookeeper | 1000 | - | ALL drop | RuntimeDefault |
| kafka-ui | 1000 | - | ALL drop | RuntimeDefault |

#### 기대 효과

| 위협 | 대응 |
|------|------|
| 컨테이너 탈출 후 호스트 장악 | runAsNonRoot — 호스트에서 root 행사 불가 |
| 악성 바이너리 삽입 | readOnlyRootFilesystem — 파일 생성 자체 차단 |
| 권한 에스컬레이션 | capabilities.drop:ALL + seccompProfile — syscall 집합 제한 |
| 비준수 Pod 배포 | PSA enforce:restricted — API 서버 수준에서 배포 자체 거부 |

---

### 5-5. Kubernetes RBAC (서비스별 전용 ServiceAccount)

#### 적용 방법

```yaml
# serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sa-currency
automountServiceAccountToken: false   # K8s API 토큰 비마운트

# deployment.yaml
spec:
  template:
    spec:
      serviceAccountName: sa-currency
      automountServiceAccountToken: false
```

| ServiceAccount | 대상 워크로드 | K8s API Role | 토큰 마운트 |
|---------------|------------|-------------|-----------|
| sa-frontend | service-frontend | 없음 | false |
| sa-currency | service-currency | 없음 | false |
| sa-history | service-history | 없음 | false |
| sa-ranking | service-ranking | 없음 | false |
| sa-dataingestor | service-dataingestor | 없음 | false |
| sa-kafka | kafka | 없음 | false |
| sa-zookeeper | zookeeper | 없음 | false |
| sa-kafka-ui | kafka-ui | 없음 | false |
| sa-kafka-exporter | kafka-exporter | 없음 | false |

#### 기대 효과

- 침해 Pod가 `/var/run/secrets/kubernetes.io/serviceaccount/token` 파일 자체를 갖지 않음
- `default` SA 공유 제거로 서비스 간 K8s API 권한 격리
- 하나의 SA 침해가 네임스페이스 전체로 확산되지 않음

---

### 5-6. 비밀 관리 (External Secrets Operator + AWS Secrets Manager)

#### 적용 방법

```
코드 → GitOps 저장소 (평문 없음)
          │
          └─ ArgoCD 적용
                │
          ExternalSecret CR
                │
     External Secrets Operator
                │
          AWS Secrets Manager   ← 실제 비밀번호 저장
                │
          K8s Secret (자동 생성, 1시간 갱신)
                │
          Pod envFrom secretRef
```

```yaml
# external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: mysql-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: mysql-secret
  data:
  - secretKey: mysql-password
    remoteRef:
      key: trip-currency/prod/mysql-secret
      property: password
```

| K8s Secret | AWS Secrets Manager 경로 | 갱신 주기 |
|-----------|------------------------|---------|
| mysql-secret | trip-currency/prod/mysql-secret | 1시간 |
| mongodb-secret | trip-currency/prod/mongodb-secret | 1시간 |
| trip-service-secrets | trip-currency/prod/trip-service-secrets | 1시간 |

**GitOps 저장소 민감 정보 처리:**

| 파일 유형 | 처리 방식 |
|---------|---------|
| `aws/iam/ebs-csi-trust.json` | .gitignore + 템플릿 파일만 커밋 |
| `aws/eks/cluster-config.yaml` | .gitignore + 템플릿 파일만 커밋 |
| `.env.aws` | .gitignore + `.env.aws.example` 커밋 |
| `grafana-admin-secret.yaml` | .gitignore (수동 생성) |
| `jenkins-setup/keys/` | .gitignore (SSH 개인키) |

#### 기대 효과

- 저장소 공개 시에도 실제 자격증명 없음
- ETCD에 평문 저장 없음 (ESO가 런타임에 주입)
- 자격증명 갱신 자동화로 수동 배포 오류 방지
- Secrets Manager 접근 이력 CloudTrail 기록

---

### 5-7. IAM 최소 권한 (IRSA)

#### 적용 방법

OIDC Provider를 통해 K8s ServiceAccount와 IAM Role을 1:1 매핑합니다. EC2 노드 IAM Role과 분리되어 Pod 수준 최소 권한을 구현합니다.

```bash
# IRSA 구성 (EBS CSI Driver 예시)
eksctl create iamserviceaccount \
  --name ebs-csi-controller-sa \
  --namespace kube-system \
  --cluster trip-service-cluster \
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
  --approve --override-existing-serviceaccounts
```

| ServiceAccount | IAM 역할 | 권한 범위 |
|---------------|---------|---------|
| ebs-csi-controller-sa | AmazonEKS_EBS_CSI_DriverRole | EBS 볼륨 프로비저닝만 |
| aws-load-balancer-controller | AWSLoadBalancerControllerRole | ALB·NLB 관리 |
| external-secrets | ExternalSecretsRole | Secrets Manager GetSecretValue만 |

#### 기대 효과

- 노드 탈취 시에도 해당 Pod SA의 최소 권한만 행사 가능
- 영구 Access Key 미사용 (OIDC 토큰, 만료 시간 짧음)
- SA별 권한 분리 — EBS CSI 침해 시 ALB 조작 불가

---

### 5-8. 저장 데이터 암호화

```yaml
# storageclass.yaml — KMS 기반 암호화 EBS
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-encrypted
parameters:
  type: gp3
  encrypted: "true"
```

| 대상 | 암호화 방식 | 상태 |
|------|-----------|------|
| EBS PV (Prometheus 20Gi, Grafana 5Gi, AlertManager 2Gi) | AWS KMS 기본 키 | ✅ 적용 |
| Aurora MySQL | 클러스터 생성 시 암호화 | ✅ 적용 |
| DocumentDB | 클러스터 생성 시 암호화 | ✅ 적용 |
| ElastiCache Redis | - | ⚠️ 미적용 (잔여 과제) |

---

### 5-9. AWS 관리형 DB 접근 통제

모든 DB에 VPC 내부 CIDR(192.168.0.0/16)만 허용하는 보안 그룹 적용 + K8s NetworkPolicy 이중 격리.

```
외부 인터넷
    │  ← AWS SG: VPC 외부 차단
    ×
  VPC 내부 (192.168.0.0/16)
    │  ← K8s NetworkPolicy: 비허가 Pod 차단
    ×
  허가된 Pod만 접근 가능
  (currency·history·ranking만 DB egress 허용)
```

---

## 6. CI/CD 파이프라인 보안

### 6-1. 파이프라인 구성

```
개발자 commit (GitHub)
        │
    Jenkins (EC2)
        │
    ┌───┴──────────────────────┐
    │  1. Docker Build          │
    │  2. ECR Push (EKS-{N})   │ ← 이미지 태그 버전 고정
    │  3. Trivy SBOM 생성       │ ← CycloneDX JSON, 아티팩트 보관
    │  4. Trivy 취약점 스캔      │ ← CRITICAL + 패치 존재 시 중단
    │  5. GitOps 저장소 업데이트 │ ← kustomization.yaml 이미지 태그 변경
    └───────────────────────────┘
                │
            ArgoCD (EKS)
                │
        자동 동기화 (Synced/Healthy)
                │
           프로덕션 배포 완료
```

### 6-2. 공급망 보안 (SBOM + Trivy)

```groovy
// Jenkinsfile.production — 5개 서비스 병렬 스캔
stage('SBOM & Vulnerability Scan') {
    parallel {
        stage('service-currency') {
            steps {
                // SBOM 생성 (CycloneDX)
                sh "trivy image --format cyclonedx \
                    --output sbom-currency.json \
                    ${ECR_REPO}/service-currency:${BUILD_TAG}"
                // CRITICAL 취약점 + 패치 존재 시 파이프라인 중단
                sh "trivy image --exit-code 1 \
                    --severity CRITICAL \
                    --ignore-unfixed \
                    ${ECR_REPO}/service-currency:${BUILD_TAG}"
            }
        }
        // ... (5개 서비스 병렬)
    }
}
```

**ECR Enhanced Scanning (AWS Inspector v2)**

```bash
aws ecr put-registry-scanning-configuration \
  --scan-type ENHANCED \
  --rules '[{"repositoryFilters":[{"filter":"*","filterType":"WILDCARD"}],
             "scanFrequency":"CONTINUOUS_SCAN"}]'
```

- ECR Push 시 자동 스캔 + 신규 CVE 등록 시 재스캔
- OS 패키지 및 언어 런타임 라이브러리 취약점 탐지

### 6-3. GitOps 보안 (ArgoCD)

```yaml
# argocd-application.yaml
spec:
  syncPolicy:
    automated:
      prune: true       # 미사용 리소스 자동 삭제
      selfHeal: true    # 수동 변경 자동 복구
    syncOptions:
      - ServerSideApply=true  # 필드 소유권 명확화
  ignoreDifferences:
    # kubectl patch로 주입한 DB 엔드포인트 보존
    - kind: ConfigMap
      jsonPointers: [/data/MYSQL_HOST, /data/MONGODB_HOST, /data/REDIS_HOST]
    # ESO 자동 생성 필드 무시
    - group: external-secrets.io
      kind: ExternalSecret
      jsonPointers: [/spec/dataFrom, /spec/data, /metadata/annotations]
    # kubectl rollout restart 어노테이션 무시
    - group: apps
      kind: Deployment
      jsonPointers: [/spec/template/metadata/annotations/kubectl.kubernetes.io~1restartedAt]
```

**효과**: 코드 저장소가 단일 진실 공급원(Single Source of Truth) — 수동 kubectl 변경이 자동으로 원복, 감사 추적 가능

---

## 7. 관측성 및 위협 탐지

### 7-1. 위협 탐지 (GuardDuty)

| 탐지 기능 | 탐지 대상 |
|---------|---------|
| CLOUD_TRAIL | 비정상 AWS API 호출, 자격증명 탈취 시도 |
| DNS_LOGS | C&C 서버 통신, 악성 도메인 쿼리 |
| FLOW_LOGS | VPC 내 비정상 트래픽 패턴 |
| EKS_AUDIT_LOGS | EKS API 비정상 접근, 권한 에스컬레이션 |
| RUNTIME_MONITORING | Pod 런타임 역쉘·프로세스·파일 위협 |
| S3_DATA_EVENTS | S3 버킷 비정상 접근·유출 |
| EBS_MALWARE_PROTECTION | EBS 볼륨 악성코드 탐지 |
| RDS_LOGIN_EVENTS | DB 비정상 로그인 시도 |

### 7-2. 메트릭 기반 알림 (PrometheusRule)

**보안 알림 규칙 (prometheus-rules-security.yaml)**

| 알림명 | 조건 | 심각도 |
|-------|------|--------|
| AbnormalPodRestartSpike | 1시간 내 재시작 5회 초과 | CRITICAL |
| UnexpectedPrivilegedContainer | `container_spec_privileged == 1` | CRITICAL |
| ContainerCPUThrottling | CPU 쓰로틀 80% 초과 15분 지속 | WARNING |
| HighNetworkEgress | Egress 10MB/s 초과 10분 지속 | WARNING |

**안정성 알림 규칙 (prometheus-rules-stability.yaml, 8개)**

PodCrashLooping / PodNotReady / DeploymentReplicasMismatch / HPAMaxReplicas / NodeHighCPU / NodeHighMemory / NodeDiskSpaceLow / PVCUsageHigh

**Kafka 알림 규칙 (prometheus-rules-kafka.yaml, 4개)**

KafkaConsumerGroupLagHigh(>1000) / KafkaConsumerGroupLagCritical(>5000) / KafkaBrokerDown / KafkaConsumerGroupNoProgress

### 7-3. 알림 라우팅

```
AlertManager
  ├─ severity: critical → #alerts-critical (Slack)
  └─ severity: warning  → #alerts-warning  (Slack)

Slack webhook URL:
  Secrets Manager → ESO → K8s Secret
  → alertmanagerSpec.secrets 마운트
  → api_url_file 경로 참조 (URL 평문 미노출)
```

### 7-4. 로그 수집 (Fluent Bit → CloudWatch)

| 스트림 | CloudWatch 로그 그룹 | 보존 |
|--------|---------------------|------|
| 애플리케이션 컨테이너 | /eks/trip-service-cluster/applications | 30일 |
| 인프라 (monitoring ns) | /eks/trip-service-cluster/infra | 14일 |
| 호스트 (kubelet/systemd) | /eks/trip-service-cluster/host | 14일 |
| EKS 컨트롤 플레인 | /aws/eks/trip-service-cluster/cluster | AWS 관리 |

### 7-5. Grafana 대시보드

| 대시보드 | 주요 패널 |
|---------|---------|
| Trip Service - Stability | Pod 재시작율, Ready 상태, HPA 스케일, 노드 CPU/Memory |
| Trip Service - Security | 비정상 재시작(1h), 네트워크 Egress, CPU 쓰로틀링, 디스크 사용률 |
| Trip Service - Kafka | Consumer Group Lag 시계열/히트맵, Broker 상태, 처리량 |

---

## 8. 보안 점검 결과 요약

### 8-1. 조치 현황

| 등급 | 항목 | 조치 전 | 조치 후 |
|------|------|--------|--------|
| CRITICAL | NetworkPolicy 미설정 | 전 Pod 상호 통신 가능 | ✅ default-deny + 12개 정책 |
| HIGH | 컨트롤 플레인 로깅 비활성화 | 감사 로그 없음 | ✅ 5개 로그 타입 전체 활성화 |
| HIGH | API 서버 0.0.0.0/0 허용 | 전 세계 인증 시도 가능 | ✅ 222.109.238.0/24로 제한 |
| HIGH | NLB HTTP 평문 노출 | HTTP 우회 경로 존재 | ✅ NLB 제거, ALB HTTPS 단일 진입 |
| HIGH | GuardDuty 미활성화 | 위협 탐지 없음 | ✅ 8개 탐지 기능 전체 활성화 |
| MEDIUM | securityContext 미설정 | root 컨테이너 실행 | ✅ runAsNonRoot + capabilities.drop:ALL |
| MEDIUM | seccompProfile 미설정 | 전체 syscall 허용 | ✅ RuntimeDefault 전 워크로드 적용 |
| MEDIUM | frontend root 실행 | uid 0, NET_BIND_SERVICE | ✅ nginx-unprivileged (uid 101, :8080) |
| MEDIUM | PSA 미적용 | 비준수 Pod 배포 가능 | ✅ enforce:restricted 적용 |
| MEDIUM | RBAC 미구성 | default SA 공유 | ✅ 전용 SA 9개 + 토큰 마운트 비활성화 |
| MEDIUM | 시크릿 코드 노출 위험 | 환경변수 하드코딩 가능성 | ✅ ESO + Secrets Manager 연동 |

### 8-2. 보안 성숙도 변화

```
적용 전                          적용 후
────────────────────────────────────────────
외부 진입점    NLB(HTTP) + ALB    →  ALB(HTTPS) 단일
네트워크 격리  없음               →  default-deny + 12개 정책
컨테이너 권한  root 실행          →  non-root, read-only FS
시크릿 관리   환경변수/하드코딩   →  ESO + AWS Secrets Manager
감사 추적     없음               →  CloudTrail + EKS Audit + FluentBit
위협 탐지     없음               →  GuardDuty (8개 기능) + AlertManager
공급망 보안   없음               →  Trivy SBOM + ECR Enhanced Scanning
```

---

## 9. 잔여 과제 및 개선 계획

| 우선순위 | 항목 | 현재 상태 | 개선 방안 |
|--------|------|---------|---------|
| 높음 | ElastiCache Redis 암호화 | AUTH·TLS 미적용 | 신규 클러스터 생성 (AUTH 토큰 + transit encryption) |
| 높음 | Prometheus Adapter | 미설치 | HPA custom metrics 공급을 위한 Adapter 설치 |
| 중간 | kafka-ui 인증 | 무인증 (NP 차단만) | BasicAuth 또는 OAuth2 설정 |
| 중간 | Kafka 고가용성 | 단일 레플리카, PVC 없음 | StatefulSet + PVC 또는 Amazon MSK 마이그레이션 |
| 낮음 | kafka-ui 이미지 태그 | :latest 사용 | 특정 버전 태그 고정 (v0.7.2 등) |

---

## 참고: 적용 기술 스택

| 영역 | 기술 |
|------|------|
| 컨테이너 오케스트레이션 | AWS EKS (Kubernetes v1.33) |
| 네트워크 정책 | Calico Tigera Operator v3.29.1 |
| 비밀 관리 | External Secrets Operator + AWS Secrets Manager |
| 위협 탐지 | AWS GuardDuty (8개 탐지 기능) |
| 모니터링 | kube-prometheus-stack (Prometheus + Grafana + AlertManager) |
| 로깅 | Fluent Bit → AWS CloudWatch Logs |
| CI/CD | Jenkins (EC2) + ArgoCD + GitOps |
| 이미지 스캔 | Trivy (SBOM + 취약점) + AWS Inspector v2 (ECR) |
| 로드밸런서 | AWS ALB (AWS Load Balancer Controller) |
| 인증서 | AWS ACM (자동 갱신) |
| 스토리지 암호화 | AWS KMS (EBS gp3-encrypted StorageClass) |
| DB 보안 | VPC 보안 그룹 + K8s NetworkPolicy 이중 격리 |
| IAM 권한 | IRSA (IAM Roles for Service Accounts, OIDC) |
