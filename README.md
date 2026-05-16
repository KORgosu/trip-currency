# Trip Service 클러스터 구조 및 보안 점검 보고서

> 클러스터: `trip-service-cluster` (EKS, ap-northeast-2)

---

## 1. 적용된 보안 전략

현재 클러스터에 실제 적용·운영 중인 보안 조치를 영역별로 정리합니다.

---

### 1-1. 네트워크 격리 (NetworkPolicy)

- **trip-currency\trip-currency-local-gitops\k8s\overlays\eks\network-policies** 에 위치
- **엔진**: Calico Tigera Operator v3.29.1 (AmazonVPC 모드, policy-engine-only — VPC CNI 유지)
- **기본 정책**: default-deny (모든 Ingress/Egress 차단 후 최소 권한만 허용)
- **적용 정책 10개** (`trip-service-prod` 네임스페이스):

| 정책 | 방향 | 허용 대상 |
|------|------|----------|
| 00-default-deny | Ingress+Egress | 전체 차단 (기본값) |
| 01-allow-dns | Egress | 전 Pod → CoreDNS :53 |
| 02-frontend | Ingress | VPC CIDR → :8080 (nginx-unprivileged, non-root) |
| 03-currency | Ingress/Egress | ALB → :8000 / Aurora·Redis·Kafka·HTTPS |
| 04-history | Ingress/Egress | ALB → :8000 / Aurora·DocDB·Redis·Kafka |
| 05-ranking | Ingress/Egress | ALB → :8000 / DocDB·Redis·Kafka |
| 06-dataingestor | Egress only | Kafka·Aurora:3306·DocDB:27017·Redis:6379·외부 HTTPS (Ingress 없음) |
| 07-kafka | Ingress/Egress | 내부 서비스 → :9092 / Zookeeper :2181 / inter-broker :9093 |
| 08-kafka-ui | Ingress 완전 차단 | Egress: Kafka·Zookeeper만 |
| 09-zookeeper | Ingress | kafka·kafka-ui → :2181만 |
| 10-allow-prometheus-scrape | Ingress | monitoring ns → :8000/:8080/:9308 |
| 11-kafka-exporter | Ingress/Egress | monitoring ns → :9308 / kafka :9092 |

**기대 효과**
- **Lateral Movement 차단**: 특정 Pod 침해 시 다른 서비스로 이동 불가 — 피해 범위가 침해된 Pod 단일 서비스로 봉쇄됨
- **C&C 통신 차단**: dataingestor 등 egress-only 서비스는 외부 악성 서버와 연결 시도 자체가 차단됨
- **DB 무단 접근 방지**: currency·history·ranking Pod만 DB egress 허용 — 침해된 dataingestor나 kafka-ui에서 Aurora·Redis로 직접 쿼리 불가
- **Blast Radius 최소화**: 공격자가 클러스터 내 임의 Pod를 장악해도 허용 목록 외 서비스에는 네트워크 도달 자체가 불가능

---

### 1-2. 외부 접근 단일화 (ALB + HTTPS 전용)

| 항목 | 내용 |
|------|------|
| 진입점 | ALB 단일 진입점 (internet-facing) |
| HTTP → HTTPS | ALB 리스너 규칙으로 80 → 443 강제 리다이렉트 |
| TLS 인증서 | ACM `*.2025teamproject.store` (SAN 포함, 자동 갱신) |
| IngressGroup | `group.name: trip-service` — trip-service-prod + monitoring 네임스페이스 단일 ALB 공유 |
| NLB 제거 | service-frontend `LoadBalancer` → `ClusterIP` 전환, HTTP 평문 우회 경로 제거 |
| 내부 서비스 | 전 서비스 ClusterIP — 클러스터 외부 직접 접근 불가 |

**기대 효과**
- **중간자 공격(MITM) 방지**: 전 구간 TLS 암호화로 전송 중 데이터 탈취·변조 불가
- **공격 표면 최소화**: HTTP 평문 포트 미노출, NLB 제거로 외부 진입점이 ALB 단일 경로로 통일
- **인증서 자동 갱신**: ACM 관리로 인증서 만료에 의한 서비스 중단 및 보안 경고 리스크 제거
- **프로토콜 다운그레이드 방지**: 80→443 강제 리다이렉트로 클라이언트가 HTTP로 접속해도 평문 구간 없음

---

### 1-3. EKS API 서버 접근 제한

| 항목 | 값 |
|------|-----|
| endpointPublicAccess | true |
| endpointPrivateAccess | true |
| publicAccessCidrs | `비공개` (사내/운영 고정 IP 대역 `/24`만 허용) |

**기대 효과**
- **자격증명 탈취 시나리오 무력화**: kubectl 비밀번호·토큰이 유출되어도 허용 CIDR 외부에서는 API 서버에 TCP 연결 자체가 불가
- **무차별 대입(Brute Force) 원천 차단**: 전 세계 임의 IP의 인증 시도를 네트워크 계층에서 차단 — API 서버 부하 없음
- **내부 전용 관리 채널 확보**: Private Access 병행 활성화로 클러스터 내부 노드→API 통신은 VPC 내부 경로 유지

---

### 1-4. AWS 관리형 DB 접근 통제

| DB | 보안 그룹 허용 CIDR | 외부 접근 |
|----|------------------|----------|
| Aurora MySQL | 192.168.0.0/16 (VPC 내부만) | 불가 |
| DocumentDB | 192.168.0.0/16 (VPC 내부만) | 불가 |
| ElastiCache Redis | 192.168.0.0/16 (VPC 내부만) | 불가 |

추가로 NetworkPolicy로 Redis/Aurora/DocDB egress를 currency·history·ranking Pod로만 제한.

**기대 효과**
- **외부 직접 공격 불가**: VPC 외부에서 DB 포트로 연결 시도 자체가 보안 그룹에서 차단 — 인증 시도조차 불가
- **이중 격리 구조**: 보안 그룹(AWS 계층) + NetworkPolicy(K8s 계층) 이중 방어로 단일 계층 우회 시에도 추가 장벽 존재
- **침해 Pod 격리**: 서비스 비즈니스 로직과 무관한 Pod(dataingestor, kafka-ui)는 DB에 물리적으로 도달 불가

---

### 1-5. 시크릿 관리 (비밀번호·키 미노출)

**런타임 (K8s 내)**
- External Secrets Operator → AWS Secrets Manager 동기화 (갱신 주기 1시간)
- K8s 매니페스트에 평문 시크릿 없음

| K8s Secret | AWS Secrets Manager 경로 |
|-----------|------------------------|
| mongodb-secret | trip-currency/prod/mongodb-secret |
| mysql-secret | trip-currency/prod/mysql-secret |
| trip-service-secrets | trip-currency/prod/trip-service-secrets |
| grafana-admin-secret | 수동 생성 (`grafana-admin-secret.yaml` — gitignore) |

**GitOps 저장소 (코드 레벨)**

| 파일 유형 | 처리 방식 |
|---------|---------|
| `aws/iam/ebs-csi-trust.json` | `.gitignore` 추가 → `ebs-csi-trust.json.template` (플레이스홀더) 커밋 |
| `aws/eks/cluster-config.yaml` | `.gitignore` 추가 → `cluster-config.yaml.template` (플레이스홀더) 커밋 |
| `aws/route53/*.json`, `aws/acm/*.json` | `.gitignore` 추가 (일회성 파일, 재사용 불필요) |
| `kube-prometheus-stack-values.yaml` | `adminPassword` 제거 → `admin.existingSecret: grafana-admin-secret` 참조 |
| `.env.aws` | `.gitignore` 추가 → `.env.aws.example` (변수명 + 값) 커밋 |

**기대 효과**
- **저장소 유출 시 피해 없음**: GitHub 저장소가 공개되어도 실제 자격증명이 없으므로 DB·인프라 직접 접근 불가
- **K8s Secret 평문 노출 방지**: 매니페스트에 하드코딩 없이 ESO가 런타임에 AWS Secrets Manager에서 주입 — ETCD에도 평문 저장 없음
- **갱신 자동화**: ESO 1시간 주기 동기화로 Secrets Manager 값 변경 시 수동 kubectl 작업 없이 자동 반영 → 운영 오류 방지
- **감사 추적**: Secrets Manager 접근 이력이 CloudTrail에 기록 — 비정상 조회 탐지 가능

---

### 1-6. IAM 최소 권한 (IRSA)

서비스 어카운트별 IAM 역할 분리 (Pod 수준 최소 권한):

| 서비스 어카운트 | IAM 역할 | 권한 범위 |
|--------------|---------|---------|
| ebs-csi-controller-sa | AmazonEKS_EBS_CSI_DriverRole | EBS 볼륨 프로비저닝만 |
| aws-load-balancer-controller | AWSLoadBalancerControllerRole | ALB·NLB 관리 + SetRulePriorities (v3) |
| external-secrets | ExternalSecretsRole | Secrets Manager GetSecretValue만 |

**기대 효과**
- **노드 탈취 시 피해 범위 제한**: EC2 인스턴스 자체가 침해되어도 노드에 부여된 IAM Role 권한이 아닌, 해당 Pod 서비스 어카운트의 최소 권한만 행사 가능
- **자격증명 자동 교체**: OIDC 토큰은 만료 기간이 짧고 자동 갱신 — 영구 Access Key 대비 탈취 유효 시간 최소화
- **책임 분리**: 서비스별 IAM 역할 분리로 EBS CSI Driver 침해 시에도 ALB 조작 불가, 반대도 동일

---

### 1-7. 저장 데이터 암호화

| 대상 | 암호화 방식 |
|------|-----------|
| EBS (PV) | gp3-encrypted StorageClass — AWS KMS 기본 키 |
| Aurora MySQL | 클러스터 생성 시 암호화 활성화 |
| DocumentDB | 클러스터 생성 시 암호화 활성화 |
| ElastiCache Redis | **미적용** (AtRestEncryptionEnabled: false) — 잔여 조치 항목 |

**기대 효과**
- **물리적 매체 탈취 무력화**: EBS 볼륨이 스냅샷 탈취·디스크 물리 접근 등으로 노출되어도 KMS 키 없이 복호화 불가
- **규정 준수**: 개인정보보호법·GDPR 등 저장 데이터 암호화 요건 충족 (PV 기반 DB 데이터 포함)
- **Aurora·DocDB 암호화**: AWS 관리형 DB의 저장 데이터, 자동 백업, 스냅샷 전체가 암호화 대상에 포함

---

### 1-8. 위협 탐지 (GuardDuty)

- **Detector ID**: `(실제 ID는 .env.aws 참조)` (ap-northeast-2)
- **Finding 발행 주기**: 6시간

활성화된 탐지 기능:

| 기능 | 상태 | 탐지 대상 |
|------|------|----------|
| CLOUD_TRAIL | ENABLED | 비정상 AWS API 호출, 자격증명 탈취 시도 |
| DNS_LOGS | ENABLED | C&C 서버 통신, 악성 도메인 쿼리 |
| FLOW_LOGS | ENABLED | VPC 내 비정상 트래픽 패턴 |
| EKS_AUDIT_LOGS | ENABLED | EKS API 서버 비정상 접근, 권한 에스컬레이션 |
| RUNTIME_MONITORING | ENABLED | EKS Pod 런타임 위협 (프로세스, 파일, 네트워크) |
| S3_DATA_EVENTS | ENABLED | S3 버킷 비정상 접근·유출 |
| EBS_MALWARE_PROTECTION | ENABLED | EBS 볼륨 악성코드 탐지 |
| RDS_LOGIN_EVENTS | ENABLED | DB 비정상 로그인 시도 |

**기대 효과**
- **사후 탐지에서 실시간 탐지로 전환**: 침해 발생 후 로그 분석이 아닌, 위협 행동 패턴 인식 즉시 알림 → 대응 시간(MTTD) 단축
- **EKS 런타임 위협 가시성**: 컨테이너 내 역쉘(Reverse Shell) 실행, 권한 에스컬레이션 시도, 비정상 프로세스 생성을 Pod 수준에서 탐지
- **자격증명 오남용 탐지**: CloudTrail 분석으로 평소와 다른 리전·시간대 API 호출, 과도한 권한 행사를 자동 감지
- **C&C 연결 탐지**: VPC Flow Logs + DNS 분석으로 알려진 악성 IP·도메인과의 통신 탐지 (NetworkPolicy 우회 시도 포함)

---

### 1-9. 공급망 보안 (SBOM)

**ECR Enhanced Scanning (AWS Inspector v2)**
- 전체 ECR 레포지토리 대상 `CONTINUOUS_SCAN` 활성화
- ECR Push 시 자동 스캔 + 신규 CVE 발표 시 재스캔
- OS 패키지 및 언어 런타임 패키지 취약점 탐지

**CI/CD 파이프라인 (Jenkinsfile.production)**

| 단계 | 도구 | 동작 |
|------|------|------|
| SBOM 생성 | Trivy | 각 서비스 이미지 → CycloneDX JSON 생성, Jenkins 아티팩트 보관 |
| 취약점 스캔 | Trivy | CRITICAL + 패치 버전 존재 시 파이프라인 중단 (`--ignore-unfixed`) |

파이프라인 실행 순서:
```
Docker Build & Push (ECR)
  → SBOM & Vulnerability Scan  ← 5개 서비스 병렬 스캔
       ├─ trivy image --format cyclonedx  → sbom-{서비스}.json
       └─ trivy image --exit-code 1 --severity CRITICAL
  → Update GitOps Repository
```

**기대 효과**
- **배포 전 취약점 차단**: CRITICAL 취약점 포함 이미지는 GitOps 저장소 업데이트 전 파이프라인이 중단 → 취약한 이미지가 프로덕션에 도달하지 않음
- **사용 컴포넌트 가시성 확보**: CycloneDX SBOM으로 각 서비스 이미지에 포함된 OS 패키지·언어 라이브러리 목록화 — 신규 CVE 발표 시 영향 서비스 즉시 파악 가능
- **지속적 모니터링**: ECR CONTINUOUS_SCAN으로 이미지 push 이후에도 새로운 CVE가 등록되면 자동 재스캔 → 배포 이후 취약점도 탐지
- **공급망 투명성**: 배포 산출물(SBOM JSON)이 Jenkins 아티팩트로 보관 — 보안 감사·규정 준수 증빙 자료로 활용 가능

---

### 1-10. Pod 컨테이너 보안 (securityContext + PSA)

모든 Deployment/CronJob에 Pod 및 컨테이너 수준 securityContext 적용. `trip-service-prod` 네임스페이스에 **Pod Security Admission `enforce=restricted`** 레이블 적용으로 비준수 Pod 배포 자체를 차단.

| 서비스 | runAsNonRoot | readOnlyRootFilesystem | allowPrivilegeEscalation | capabilities | seccompProfile |
|--------|-------------|----------------------|------------------------|-------------|---------------|
| frontend | ✅ (uid 101) | ✅ | false | ALL drop | RuntimeDefault |
| currency | ✅ (uid 1000) | ✅ | false | ALL drop | RuntimeDefault |
| history | ✅ (uid 1000) | ✅ | false | ALL drop | RuntimeDefault |
| ranking | ✅ (uid 1000) | ✅ | false | ALL drop | RuntimeDefault |
| kafka | ✅ (uid 1000) | - | false | ALL drop | RuntimeDefault |
| zookeeper | ✅ (uid 1000) | - | false | ALL drop | RuntimeDefault |
| kafka-ui | ✅ (uid 1000) | - | false | ALL drop | RuntimeDefault |
| dataingestor | ✅ (uid 1000) | ✅ | false | ALL drop | RuntimeDefault |

`readOnlyRootFilesystem` 적용 서비스는 emptyDir 볼륨으로 쓰기 경로 확보 (`/tmp`, `/app/logs`, nginx 임시 경로).
frontend는 `nginx:alpine`(root 필수) 대신 `nginxinc/nginx-unprivileged:alpine`(uid 101, :8080)으로 전환하여 `runAsNonRoot` 및 `NET_BIND_SERVICE` 예외 없이 PSA restricted 완전 준수.

**PSA 네임스페이스 레이블 (`k8s/overlays/eks/namespace.yaml`)**
```yaml
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/warn: restricted
```

**기대 효과**
- **정책 강제 (enforce)**: 매니페스트에 securityContext를 설정해도 PSA 기준 미달 Pod는 API 서버에서 즉시 거부 — kubectl/ArgoCD 양쪽 경로 모두 차단
- **컨테이너 탈출 후 영향 최소화**: `runAsNonRoot`로 탈출해도 호스트에서 root 권한 행사 불가 — 노드 전체 장악 시나리오 차단
- **파일시스템 변조 방지**: `readOnlyRootFilesystem`으로 악성 바이너리 생성·스크립트 삽입 불가 — 지속성(Persistence) 확보 난이도 상승
- **커널 공격 표면 축소**: `capabilities.drop: ALL` + `seccompProfile: RuntimeDefault`으로 허용 syscall 집합을 OS 기본 프로파일로 제한 — 권한 에스컬레이션 익스플로잇 효과 감소
- **감사·경고 가시성**: audit/warn 레이블로 정책 위반 시도가 감사 로그와 API 응답에 기록

---

### 1-11. Kubernetes RBAC (인-클러스터 접근 제어)

서비스별 전용 ServiceAccount를 생성하고 K8s API 토큰 자동 마운트를 비활성화하여, 침해된 Pod가 클러스터 내부 리소스에 접근하는 경로를 원천 차단.

| ServiceAccount | 대상 워크로드 | K8s API 접근 | automountToken |
|---------------|-------------|------------|---------------|
| sa-frontend | service-frontend | 없음 | false |
| sa-currency | service-currency | 없음 | false |
| sa-history | service-history | 없음 | false |
| sa-ranking | service-ranking | 없음 | false |
| sa-dataingestor | service-dataingestor (CronJob) | 없음 | false |
| sa-kafka | kafka | 없음 | false |
| sa-zookeeper | zookeeper | 없음 | false |
| sa-kafka-ui | kafka-ui | 없음 | false |
| sa-kafka-exporter | kafka-exporter | 없음 | false |

모든 앱 서비스는 K8s API를 직접 호출하지 않으므로 Role/RoleBinding 없이 토큰 마운트만 비활성화. 인프라 컴포넌트(ALB Controller, ESO, EBS CSI)는 이미 IRSA로 별도 관리.

**기대 효과**
- **K8s API 토큰 탈취 차단**: `automountServiceAccountToken: false`로 Pod 내부에 토큰 파일(`/var/run/secrets/kubernetes.io/serviceaccount/token`) 자체가 생성되지 않음 — 컨테이너 침해 후 토큰을 이용한 K8s API 호출 불가
- **Lateral Movement 차단**: `default` SA 공유 제거로 침해된 Pod가 타 서비스 리소스(ConfigMap, Secret, Pod 목록 등)를 조회·수정하는 경로 차단
- **최소 권한 원칙**: 각 서비스가 자신의 SA만 보유 — 하나의 SA 침해가 네임스페이스 전체로 확산되지 않음

---

### 1-12. 관측성 (모니터링·로깅)

**메트릭 수집 (monitoring 네임스페이스)**
- Prometheus: trip-service-prod 전 Pod scrape (`prometheus.io/scrape: "true"` 어노테이션), retention 15d
- kafka-exporter: `danielqsj/kafka-exporter:v1.7.0` — Kafka Consumer Lag·Broker 상태 메트릭을 :9308에서 노출, Prometheus가 자동 수집
- Grafana: `https://grafana.2025teamproject.store` (ALB HTTPS), sidecar 자동 임포트 (label: `grafana_dashboard: "1"`)
- AlertManager: gp3-encrypted 스토리지, Slack 수신 설정 (#alerts-critical / #alerts-warning)

**Grafana 대시보드 (ConfigMap 자동 임포트)**

| 대시보드 | UID | 주요 패널 |
|---------|-----|---------|
| Trip Service - Stability | trip-stability | Pod 재시작율, Ready 상태, Deployment 레플리카, HPA, Node CPU/Memory, 컨테이너 리소스 |
| Trip Service - Security | trip-security | 비정상 재시작(1h), 네트워크 Egress/Ingress, CPU 스로틀링, Disk 사용률 |
| Trip Service - Kafka | trip-kafka | Consumer Group Lag (시계열/히트맵), 오프셋 커밋 속도, Broker 수, Topic 처리량 |

**AlertManager 알림 규칙 (PrometheusRule)**

| 파일 | 알림 수 | 주요 알림 |
|------|--------|---------|
| prometheus-rules-stability.yaml | 8개 | PodCrashLooping, PodNotReady, DeploymentReplicasMismatch, HPAMaxReplicas, NodeHighCPU, NodeHighMemory, NodeDiskSpaceLow, PVCUsageHigh |
| prometheus-rules-security.yaml | 4개 | AbnormalPodRestartSpike, ContainerCPUThrottling, HighNetworkEgress, UnexpectedPrivilegedContainer |
| prometheus-rules-kafka.yaml | 4개 | KafkaConsumerGroupLagHigh(>1000), KafkaConsumerGroupLagCritical(>5000), KafkaBrokerDown, KafkaConsumerGroupNoProgress |

**AlertManager Slack 라우팅**
- `severity: critical` → `#alerts-critical` 채널
- `severity: warning` → `#alerts-warning` 채널
- Slack webhook URL: AWS Secrets Manager `trip-currency/prod/alertmanager-slack` → ESO → K8s Secret `alertmanager-slack-webhook` → `alertmanagerSpec.secrets` 마운트 → `api_url_file` 경로 참조 (URL 평문 노출 없음)

**로그 (logging 네임스페이스)**

| Fluent Bit 스트림 | CloudWatch 로그 그룹 | 보존 |
|-----------------|--------------------|----|
| 애플리케이션 컨테이너 | /eks/trip-service-cluster/applications | 30일 |
| 인프라(monitoring ns) | /eks/trip-service-cluster/infra | 14일 |
| 호스트(kubelet/systemd) | /eks/trip-service-cluster/host | 14일 |

**EKS 컨트롤 플레인 로그** → CloudWatch `/aws/eks/trip-service-cluster/cluster`
- api, audit, authenticator, controllerManager, scheduler 전체 활성화

**기대 효과**
- **보안 인시던트 가시성 확보**: Prometheus 메트릭 이상 + CloudWatch 로그 + GuardDuty Finding을 조합해 공격 시도를 다각도로 탐지 가능
- **감사 추적(Audit Trail)**: EKS audit 로그로 클러스터 내 모든 API 호출 기록 보존 — 침해 사고 사후 분석 및 책임 추적 가능
- **비정상 트래픽 조기 발견**: Prometheus + Grafana 대시보드로 요청량·응답 시간 급변을 실시간 시각화 — DoS·이상 부하 조기 인지
- **컨트롤 플레인 로그 중앙화**: 노드 장애·파드 재시작 이력이 CloudWatch에 보존 — 로그 삭제 시도에도 증거 보전

---

## 2. 보안 점검 요약

| 등급 | 항목 | 상태 |
|------|------|------|
| CRITICAL | NetworkPolicy 미설정 | ✅ 조치완료 |
| HIGH | 컨트롤 플레인 로깅 비활성화 | ✅ 조치완료 |
| HIGH | API 서버 0.0.0.0/0 허용 | ✅ 조치완료 (허용 CIDR 비공개) |
| HIGH | NLB 중복 노출 | ✅ 조치완료 |
| HIGH | GuardDuty 미활성화 | ✅ 조치완료 |
| MEDIUM | securityContext 미설정 | ✅ 조치완료 (runAsNonRoot·readOnlyRootFilesystem·capabilities.drop) |
| MEDIUM | seccompProfile 미설정 | ✅ 조치완료 (전 워크로드 RuntimeDefault) |
| MEDIUM | frontend root 실행 | ✅ 조치완료 (nginx-unprivileged:alpine, uid 101, :8080) |
| MEDIUM | Pod Security Admission 미적용 | ✅ 조치완료 (enforce=restricted, trip-service-prod) |
| MEDIUM | Kubernetes RBAC 미구성 | ✅ 조치완료 (전용 SA + automountServiceAccountToken: false) |
| MEDIUM | kafka-ui 무인증 접근 | ⚠️ 부분조치 (NP 차단, Auth 미설정) |
| MEDIUM | HPA 메트릭 미작동 | ⚠️ 부분조치 (Prometheus 설치, Adapter 미설치) |
| MEDIUM | Redis 인증·암호화 미설정 | ❌ 미조치 (클러스터 재생성 필요) |
| MEDIUM | latest 태그 / Kafka 가용성 | ❌ 미조치 |
| LOW | dataingestor 파이프라인 연결 문제 | ✅ 조치완료 |

---

## 3. 잔여 조치 권고 순서

1. **Prometheus Adapter 설치** — HPA custom metrics 공급 완성
2. **kafka-ui Basic Auth 설정** — 내부 무인증 UI 차단
3. **frontend-config API URL 수정** — dev URL → `https://2025teamproject.store`
4. **Redis AUTH 토큰 + TLS 활성화** — 클러스터 재생성 필요, 데이터 마이그레이션 계획 수립

---

## 4. 클러스터 전체 구조

### 4-1. EKS 클러스터

| 항목 | 값 |
|------|-----|
| 클러스터명 | trip-service-cluster |
| Kubernetes 버전 | v1.33 (EKS platform: eks.37) |
| 리전 | ap-northeast-2 (서울) |
| VPC | vpc-xxxxxxxxxxxxxxxx (CIDR: 192.168.0.0/16) |
| 노드 그룹 | trip-service-workers (t3.medium x 3, min:2 / max:5) |
| 노드 OS | Amazon Linux 2023 (nodeadm) |
| 인증 모드 | API_AND_CONFIG_MAP |
| OIDC | 활성화됨 (IRSA 사용) |
| VPC Prefix Delegation | 활성화됨 (ENABLE_PREFIX_DELEGATION=true) |
| max-pods (노드당) | 110 (Launch Template v2, NodeConfig maxPods:110) |
| 컨트롤 플레인 로깅 | api, audit, authenticator, controllerManager, scheduler 전체 활성화 |

### 4-2. 애플리케이션 서비스 (namespace: `trip-service-prod`)

| 서비스 | 이미지 | 레플리카 | 타입 | 포트 | HPA |
|--------|--------|----------|------|------|-----|
| service-frontend | ECR:latest | 3 | ClusterIP + Ingress | 8080 | min:1 / max:12 |
| service-currency | ECR:latest | 2 | ClusterIP | 8000 | min:1 / max:10 |
| service-history | ECR:latest | 2 | ClusterIP | 8000 | min:1 / max:8 |
| service-ranking | ECR:latest | 2 | ClusterIP | 8000 | min:1 / max:8 |
| kafka | confluentinc/cp-kafka:7.4.0 | 1 | ClusterIP | 9092 | 없음 |
| kafka-ui | provectuslabs/kafka-ui:latest | 1 | ClusterIP | 8080 | 없음 |
| kafka-exporter | danielqsj/kafka-exporter:v1.7.0 | 1 | ClusterIP | 9308 | 없음 |
| zookeeper | confluentinc/cp-zookeeper:7.4.0 | 1 | ClusterIP | 2181 | 없음 |
| service-dataingestor | ECR:latest | - | CronJob (*/5 * * * *) | - | - |

### 4-3. 데이터베이스 계층 (AWS 관리형)

| DB | 엔진 | 엔드포인트 | 포트 | 접근 허용 CIDR |
|----|------|-----------|------|---------------|
| trip-aurora-cluster | Aurora MySQL | trip-aurora-cluster.cluster-xxxxxxxxxx.ap-northeast-2.rds.amazonaws.com | 3306 | 192.168.0.0/16 |
| trip-docdb-cluster | DocumentDB (MongoDB 호환) | trip-docdb-cluster.cluster-xxxxxxxxxx.ap-northeast-2.docdb.amazonaws.com | 27017 | 192.168.0.0/16 |
| trip-redis-cluster | ElastiCache Redis | trip-redis-cluster.xxxxxx.0001.apn2.cache.amazonaws.com | 6379 | 192.168.0.0/16 |

모든 DB 보안 그룹은 VPC 내부 CIDR(192.168.0.0/16)만 허용하며 외부 직접 접근 불가.

### 4-4. 네트워크 / 인그레스

```
인터넷
  ├─ Route53: 2025teamproject.store         (A Alias) ─┐
  └─ Route53: grafana.2025teamproject.store (A Alias) ─┤
                                                        │
       └─ ALB: trip-service-alb (internet-facing)  ←──┘  단일 ALB (IngressGroup: trip-service)
            ├─ HTTP:80  → HTTPS:443 리다이렉트
            └─ HTTPS:443 (ACM *.2025teamproject.store)
                 ├─ host: grafana.2025teamproject.store
                 │    └─ /  → kube-prometheus-stack-grafana:80 (monitoring ns)
                 ├─ host: 2025teamproject.store
                 │    ├─ /                   → service-frontend:80   (ClusterIP)
                 │    ├─ /api/v1/currencies  → service-currency:8000 (ClusterIP)
                 │    ├─ /api/v1/history     → service-history:8000  (ClusterIP)
                 │    ├─ /api/v1/rankings    → service-ranking:8000  (ClusterIP)
                 │    └─ /health             → service-currency:8000 (ClusterIP)

※ 과거 NLB(이름 비공개) 제거됨 — HTTP 평문 우회 경로 없음
※ ACM 인증서 SAN: 2025teamproject.store, *.2025teamproject.store (별도 발급 불필요)
```

### 4-5. 인프라 컴포넌트

#### kube-system

| 컴포넌트 | 역할 | 상태 |
|---------|------|------|
| AWS Load Balancer Controller | ALB/NLB 프로비저닝 | Running x 2 |
| External Secrets Operator | AWS Secrets Manager → K8s Secret 동기화 | Running x 3 |
| CoreDNS | 클러스터 내부 DNS | Running x 2 |
| aws-node (VPC CNI) | Pod 네트워킹 (Prefix Delegation) | DaemonSet x 3 |
| Calico (Tigera Operator) | NetworkPolicy 엔진 (policy-only, VPC CNI 유지) | Running |
| EBS CSI Driver | EBS 볼륨 프로비저닝 (IRSA: AmazonEKS_EBS_CSI_DriverRole) | DaemonSet x 3 |
| gp3-encrypted StorageClass | 암호화 EBS gp3 동적 프로비저닝 | 기본값 |

#### monitoring (namespace: `monitoring`)

| 컴포넌트 | 역할 | 스토리지 |
|---------|------|---------|
| Prometheus | 메트릭 수집·저장 (retention: 15d) | gp3-encrypted 20Gi |
| Grafana | 대시보드 시각화 (admin: K8s Secret `grafana-admin-secret` 참조) | gp3-encrypted 5Gi |
| AlertManager | 알림 라우팅 (Slack #alerts-critical / #alerts-warning) | gp3-encrypted 2Gi |
| node-exporter | 노드 메트릭 수집 | DaemonSet x 3 |
| kube-state-metrics | Deployment/Pod 상태 메트릭 | - |

- 스크래핑: `prometheus.io/scrape: "true"` 어노테이션 기반으로 trip-service-prod 파드 자동 수집 (포트 8000·8080·9308)
- kafka-exporter: `danielqsj/kafka-exporter:v1.7.0` — Consumer Lag·Broker 메트릭 제공 (trip-service-prod 네임스페이스 배포)
- Grafana 자동 대시보드: `grafana_dashboard: "1"` 레이블 ConfigMap sidecar 자동 임포트 (Stability·Security·Kafka 3종)
- PrometheusRule: stability 8개·security 4개·kafka 4개 알림 규칙 (monitoring 네임스페이스)
- AlertManager Slack webhook: ESO → `alertmanager-slack-webhook` Secret → `api_url_file` 마운트 (평문 미노출)
- Grafana 외부 접근: `https://grafana.2025teamproject.store` (ALB HTTPS, IngressGroup 공유)

#### logging (namespace: `logging`)

| 컴포넌트 | 역할 | CloudWatch 로그 그룹 | 보존 |
|---------|------|---------------------|------|
| Fluent Bit | 컨테이너 로그 수집 → CloudWatch | /eks/trip-service-cluster/applications | 30일 |
| Fluent Bit | 인프라 로그 (monitoring 네임스페이스) | /eks/trip-service-cluster/infra | 14일 |
| Fluent Bit | 호스트 로그 (kubelet/systemd) | /eks/trip-service-cluster/host | 14일 |

### 4-6. 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│ AWS ap-northeast-2                                                    │
│                                                                       │
│  Route53: 2025teamproject.store         ──┐                          │
│  Route53: grafana.2025teamproject.store ──┤                          │
│                                           ▼                          │
│  ┌────────────────────────────────────────────┐                      │
│  │ ALB: trip-service-alb (internet-facing)     │ IngressGroup         │
│  │ HTTP→HTTPS 리다이렉트 / ACM *.2025teamproject│ trip-service         │
│  └────┬───────────────────────────────────────┘                      │
│       │ HTTPS:443                                                     │
│  ┌────▼──────────────────────────────────────────────────────────┐   │
│  │ VPC: 192.168.0.0/16                                            │   │
│  │                                                                │   │
│  │  ┌─────────────── EKS trip-service-cluster ─────────────────┐ │   │
│  │  │                                                           │ │   │
│  │  │  [trip-service-prod]          [NetworkPolicy: 적용됨]     │ │   │
│  │  │  ┌─────────────────┐  ┌──────────┐  ┌──────────┐        │ │   │
│  │  │  │ frontend        │  │ currency │  │ history  │        │ │   │
│  │  │  │ ClusterIP :80   │  │ ClusterIP│  │ ClusterIP│        │ │   │
│  │  │  │ (NLB 제거됨)    │  │ :8000    │  │ :8000    │        │ │   │
│  │  │  └─────────────────┘  └──────────┘  └──────────┘        │ │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │ │   │
│  │  │  │ ranking  │  │  kafka   │  │ kafka-ui │               │ │   │
│  │  │  │ :8000    │  │ :9092    │  │ :8080    │               │ │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘               │ │   │
│  │  │  ┌──────────┐  ┌────────────┐                            │ │   │
│  │  │  │zookeeper │  │dataingestor│                            │ │   │
│  │  │  │ :2181    │  │ (CronJob)  │                            │ │   │
│  │  │  └──────────┘  └────────────┘                            │ │   │
│  │  │                                                           │ │   │
│  │  │  [monitoring]                        [logging]            │ │   │
│  │  │  ┌───────────────────────────┐    ┌──────────────────┐   │ │   │
│  │  │  │ Prometheus (20Gi)         │    │ Fluent Bit DS x3 │   │ │   │
│  │  │  │ Grafana (5Gi) ← ALB ingress    │  → CloudWatch   │   │ │   │
│  │  │  │  grafana.2025teamproject  │    └──────────────────┘   │ │   │
│  │  │  │ AlertManager (2Gi)        │                            │ │   │
│  │  │  │ node-exporter (DS x3)     │                            │ │   │
│  │  │  │ kube-state-metrics        │                            │ │   │
│  │  │  └───────────────────────────┘                            │ │   │
│  │  │                                                           │ │   │
│  │  │  [kube-system]                                            │ │   │
│  │  │  ALB Controller │ External Secrets │ CoreDNS              │ │   │
│  │  │  aws-node (VPC CNI + Prefix Delegation, max-pods:110)     │ │   │
│  │  │  Calico (policy-engine) │ EBS CSI Driver                  │ │   │
│  │  └───────────────────────────────────────────────────────────┘ │   │
│  │                                                                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │   │
│  │  │ Aurora   │  │ DocDB    │  │ Redis    │  (VPC-only 접근)   │   │
│  │  │ MySQL    │  │ MongoDB  │  │Elasticache│                   │   │
│  │  └──────────┘  └──────────┘  └──────────┘                    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  CloudWatch Logs: /eks/trip-service-cluster/{applications,infra,host} │
│  Secrets Manager: trip-currency/prod/* (ESO 1h 갱신)                  │
│  EKS Control Plane Logs: api, audit, authenticator, ctrl, scheduler   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4-7. 시크릿 관리

External Secrets Operator를 통해 AWS Secrets Manager에서 자동 동기화 (갱신 주기: 1시간):

| K8s Secret 명 | ASM 경로 |
|--------------|---------|
| mongodb-secret | trip-currency/prod/mongodb-secret |
| mysql-secret | trip-currency/prod/mysql-secret |
| trip-service-secrets | trip-currency/prod/trip-service-secrets |

---

## 5. 보안 점검 상세

### ✅ [CRITICAL → 조치완료] NetworkPolicy 미설정

- **조치일**: 2026-05-14
- **조치 내용**: Calico Tigera Operator v3.29.1 설치 (AmazonVPC 모드, policy-engine-only). 10개 NetworkPolicy 적용

---

### ✅ [HIGH → 조치완료] EKS 컨트롤 플레인 로깅 전체 비활성화

- **조치일**: 2026-05-14
- **조치 내용**: `aws eks update-cluster-config`로 5개 로그 타입 전체 활성화
  - api, audit, authenticator, controllerManager, scheduler → enabled: true
  - CloudWatch 로그 그룹: `/aws/eks/trip-service-cluster/cluster`

---

### ✅ [HIGH → 조치완료] EKS API 서버 공개 엔드포인트가 0.0.0.0/0 허용

- **조치일**: 2026-05-15
- **조치 내용**: `publicAccessCidrs` 0.0.0.0/0 → 사내/운영 고정 대역(비공개 `/24`)으로 제한
  ```bash
  aws eks update-cluster-config --name trip-service-cluster \
    --resources-vpc-config endpointPublicAccess=true,endpointPrivateAccess=true,publicAccessCidrs="<YOUR_ALLOWED_CIDR>"
  ```
- **결과**: 전 세계 임의 접근 차단. 허용 CIDR 외부에서는 EKS API 서버 인증 시도 불가
- **주의**: 운영 IP 대역 변경 시 위 명령으로 재설정 필요

---

### ✅ [HIGH → 조치완료] service-frontend가 NLB로도 직접 노출됨

- **조치일**: 2026-05-15
- **조치 내용**: service-frontend 타입 `LoadBalancer` → `ClusterIP` 변경. NLB(식별자 비공개) 자동 삭제 완료
- **결과**: 외부 접근 경로가 ALB(HTTPS) 단일 진입점으로 통일. HTTP 평문 우회 경로 제거

---

### ✅ [MEDIUM → 조치완료] Pod securityContext + Pod Security Admission 설정 (전 서비스)

- **조치일**: 2026-05-15
- **조치 내용 (1차)**: 전 Deployment/CronJob에 Pod 및 컨테이너 수준 securityContext 적용
  - Pod 수준: `runAsNonRoot: true`, `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`
  - 컨테이너 수준: `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`
- **조치 내용 (2차, 2026-05-15)**: PSA `restricted` 완전 준수를 위한 추가 조치
  - **전 워크로드**: Pod 수준 `seccompProfile: {type: RuntimeDefault}` 추가 (PSA restricted 필수 요건)
  - **frontend**: `nginx:alpine`(root 필수, :80) → `nginxinc/nginx-unprivileged:alpine`(uid 101, :8080)으로 이미지 전환
    - `runAsNonRoot: true`, `runAsUser: 101` 적용 가능
    - `NET_BIND_SERVICE` capability 제거 (포트 8080은 비특권 포트 — nginx-unprivileged 기본 포트)
    - Service `targetPort: 8080`, NetworkPolicy `port: 8080`으로 연동 수정
  - **kafka/zookeeper/kafka-ui**: 데이터 기록 필요로 `readOnlyRootFilesystem` 미적용 (PSA restricted 비필수 항목)
  - **Namespace**: `pod-security.kubernetes.io/enforce: restricted` 레이블 적용 → 기준 미달 Pod 배포 차단
- **결과**: 전 서비스 PSA restricted 완전 준수. API 서버 수준에서 비준수 Pod 배포 자체를 차단

---

### ⚠️ [MEDIUM → 부분조치] kafka-ui에 인증 없이 클러스터 내부 접근 가능

- **조치일**: 2026-05-14
- **조치 내용**: NetworkPolicy `08-kafka-ui.yaml`로 외부 Pod로부터의 ingress 완전 차단
- **미완료**: kafka-ui 자체 Basic Auth / OAuth 인증 설정 미적용 (내부 침해 시 여전히 무인증 UI 접근 가능)
- **잔여 권고**: kafka-ui Helm values에 인증 설정 추가
  ```yaml
  KAFKA_CLUSTERS_0_KAFKACONNECT_0_AUTH_TYPE: "LOGIN_FORM"
  ```

---

### [MEDIUM] frontend-config에 잘못된 API URL 잔존

- **현상**: frontend-config ConfigMap에 api-base-url: http://api-dev.trip-service.local — dev 환경 URL이 prod 네임스페이스에 설정됨
- **영향**: 프론트엔드가 이 값을 사용할 경우 API 호출 실패 또는 잘못된 엔드포인트로 요청
- **권고**: `https://2025teamproject.store` 로 수정 또는 불필요 시 제거 확인 필요

---

### ✅ [MEDIUM → 조치완료] Kubernetes RBAC 미구성

- **조치일**: 2026-05-15
- **조치 내용**: 전 워크로드에 전용 ServiceAccount 생성 및 K8s API 토큰 마운트 비활성화
  - 서비스별 전용 SA 생성: `sa-frontend`, `sa-currency`, `sa-history`, `sa-ranking`, `sa-dataingestor`, `sa-kafka`, `sa-zookeeper`, `sa-kafka-ui`
  - 전 Deployment/CronJob에 `serviceAccountName` 지정
  - SA 및 Pod spec 양쪽에 `automountServiceAccountToken: false` 적용
- **결과**: 침해된 Pod가 K8s API 토큰으로 클러스터 내부 리소스에 접근하는 경로 차단. `default` SA 공유 제거로 서비스 간 권한 격리 완성

---

### ⚠️ [MEDIUM → 부분조치] HPA가 메트릭을 수집하지 못함

- **조치일**: 2026-05-14
- **조치 내용**: kube-prometheus-stack 설치 (Prometheus, Grafana, AlertManager, node-exporter, kube-state-metrics). trip-service-prod 파드 자동 스크래핑 설정 완료
- **미완료**: Prometheus Adapter 미설치 — HPA가 Prometheus 메트릭을 custom metrics API로 소비하려면 Adapter 필요
- **잔여 권고**:
  ```bash
  helm install prometheus-adapter prometheus-community/prometheus-adapter \
    --namespace monitoring \
    --set prometheus.url=http://kube-prometheus-stack-prometheus.monitoring.svc
  ```

---

### [MEDIUM] ElastiCache Redis 인증 및 암호화 미설정

- **현상**: `trip-redis-cluster` 생성 시 AUTH 토큰, 전송 암호화(TLS), 저장 암호화 모두 비활성화
  - AuthTokenEnabled: false
  - TransitEncryptionEnabled: false
  - AtRestEncryptionEnabled: false
- **현재 방어선**: NetworkPolicy로 currency/history/ranking Pod에서만 Redis egress 허용. VPC 외부 직접 접근 불가
- **영향**: 해당 Pod 침해 시 인증 없이 Redis 데이터 전체 접근·수정 가능. 전송 중 데이터 평문 노출
- **권고**: AUTH 토큰 + TLS 활성화. 단, ElastiCache는 in-place 변경 불가 — 클러스터 재생성 및 데이터 마이그레이션 필요
  1. 새 클러스터 생성 (`--auth-token`, `--transit-encryption-enabled`)
  2. AUTH 토큰을 AWS Secrets Manager에 저장 후 ExternalSecret으로 주입
  3. 서비스 연결 전환 후 구 클러스터 삭제

---

### [MEDIUM] kafka-ui 이미지 태그 :latest 사용

- **현상**: provectuslabs/kafka-ui:latest — 버전 고정 없음
- **영향**: Pod 재시작 시 예측 불가능한 버전으로 업데이트될 수 있음
- **권고**: 특정 버전 태그로 고정 (예: v0.7.2)

---

### [MEDIUM] Kafka/Zookeeper 단일 레플리카 + 영구 볼륨(PVC) 없음

- **현상**: kafka, zookeeper 모두 replicas: 1이며 PVC 미사용
- **영향**: Pod 재시작 또는 노드 장애 시 Kafka 메시지 전체 유실, 서비스 중단
- **권고**: StatefulSet + PVC 전환 또는 Amazon MSK 마이그레이션 검토

---

### ✅ [LOW → 조치완료] dataingestor 파이프라인 전체 연결 문제

- **조치일**: 2026-05-16
- **원인 및 조치 내용**:
  1. **ConfigMap 플레이스홀더** — `kubectl apply -k` 사용 시 `${AURORA_ENDPOINT}` 등 미치환으로 MySQL 연결 실패. `kubectl patch`로 실제 엔드포인트 적용
  2. **NetworkPolicy 누락** — `06-dataingestor.yaml`에 Aurora:3306·DocDB:27017·Redis:6379 egress 없음 → 추가
  3. **DB 스키마 미초기화** — Aurora에 테이블 없음 → `db-init-job.yaml` 생성 및 실행 (스키마 + 통화 마스터 70개)
  4. **Kafka inter-broker 차단 (available brokers: 0)** — EKS hairpin routing 문제로 controller가 `service-kafka:9092`(ClusterIP)로 자신에게 접속 실패 → Kafka 리스너를 INTERNAL(pod IP:9093) / EXTERNAL(service-kafka:9092)로 분리, `07-kafka.yaml`에 pod CIDR:9093 egress 추가
  5. **ExchangeRate-API v6 마이그레이션** — 무료 v4 → 유료 v6, API 키를 Secrets Manager에 저장 후 CronJob 환경변수로 주입
  6. **currencies 테이블 PLN 누락** — `init-db.sql` 및 DB에 폴란드 즐로티 추가
- **결과**: ExchangeRate-API v6에서 70개 통화 수집 → MySQL 70건 저장 → Kafka 73개 이벤트 발행. Job status: **Complete**

---

### ✅ [운영 버그 → 조치완료] frontend 포트 8080 → 80 수정 (504 Gateway Timeout)

- **조치일**: 2026-05-16
- **원인**: `nginx-unprivileged` 이미지는 :80에서 Listen하지만 Deployment(containerPort), Service(targetPort), NetworkPolicy(ingress port)가 모두 :8080으로 설정되어 있어 ALB → Pod 트래픽이 차단됨
- **조치 내용**:
  - `k8s/base/services/frontend/deployment.yaml`: `containerPort`, livenessProbe/readinessProbe `port` → 80
  - `k8s/base/services/frontend/service.yaml`: `targetPort` → 80
  - `k8s/overlays/eks/network-policies/02-frontend.yaml`: ingress `port` → 80
- **결과**: 신규 Pod 즉시 1/1 Running, 504 오류 해소

---

### ✅ [운영 버그 → 조치완료] service-ranking DocumentDB 전환 및 버그 수정

- **조치일**: 2026-05-16
- **배경**: EKS 환경에서 DynamoDB 테이블이 존재하지 않고 IRSA도 미설정 상태. `DynamoDBHelper` 코드가 Mock 구현이었음에도 인수 전달 방식 오류로 초기화 자체가 실패
- **조치 내용**:
  1. **DynamoDBHelper init 버그** — `DynamoDBHelper(table_name)` 호출 시 `__init__()` 파라미터 없어 TypeError → `table_name: str = None` 추가
  2. **스케줄러 logger 버그** — `logger.info(..., correlation_id=...)` 형태의 keyword arg가 표준 Python logging에서 지원되지 않아 자정 daily reset 크래시 → f-string 인라인 방식으로 변경
  3. **ranking_provider, selection_recorder** — `initialize()` 메서드에서 `DynamoDBHelper` 완전 제거, DocumentDB 모드로 전환
  4. **mongodb_service.py** — `ranking_results` 컬렉션 및 `upsert_ranking_result` / `get_ranking_result` / `list_ranking_results` 메서드 추가
  5. **main.py** — `/api/v1/rankings/update` 등 스토어 엔드포인트가 DocumentDB `country_clicks` / `ranking_results` 컬렉션을 직접 사용하도록 재구현
- **결과**: 신규 Pod 기동 로그 — "SelectionRecorder initialized (DocumentDB mode)", "MongoDB connected successfully", 스케줄러 정상 기동

---

## 6. 주요 인프라 변경 이력

| 항목 | 내용 |
|------|------|
| Calico CNI | Tigera Operator v3.29.1, AmazonVPC 모드 (policy-engine-only) |
| NetworkPolicy | 10개 정책, default-deny 기반 최소 권한 |
| EKS 컨트롤 플레인 로깅 | api/audit/authenticator/controllerManager/scheduler 전체 활성화 |
| EKS API 서버 CIDR | 0.0.0.0/0 → 사내 허용 대역(비공개)으로 제한 |
| kube-prometheus-stack | Prometheus + Grafana + AlertManager + node-exporter + kube-state-metrics |
| Grafana 외부 접근 | https://grafana.2025teamproject.store (ALB IngressGroup 공유, ACM *.2025teamproject.store) |
| ALB IngressGroup | group.name: trip-service — 단일 ALB로 trip-service-prod + monitoring 네임스페이스 Ingress 통합 |
| ALB IAM 정책 v3 | AWSLoadBalancerControllerPolicy에 elasticloadbalancing:SetRulePriorities 추가 |
| service-frontend | LoadBalancer → ClusterIP 변경, NLB 제거 (HTTP 평문 우회 경로 제거) |
| Fluent Bit | DaemonSet → CloudWatch Logs (applications 30일 / infra·host 14일) |
| EBS CSI Driver | EKS addon + IRSA (AmazonEKS_EBS_CSI_DriverRole) |
| gp3-encrypted StorageClass | 암호화 EBS gp3 동적 프로비저닝 |
| VPC Prefix Delegation | ENABLE_PREFIX_DELEGATION=true, max-pods: 17 → 110 |
| Launch Template v2 | AL2023 NodeConfig maxPods:110, 노드 그룹 롤링 업데이트 완료 |
| ECR Enhanced Scanning | AWS Inspector v2 CONTINUOUS_SCAN 활성화 (전체 레포지토리) |
| SBOM 파이프라인 | Jenkinsfile.production에 Trivy SBOM 생성 + CRITICAL 취약점 차단 스테이지 추가 |
| GuardDuty | Detector 활성화 (CloudTrail, DNS, VPC Flow, EKS Audit, Runtime, S3, EBS, RDS 전체 활성화) |
| Pod securityContext | 전 Deployment/CronJob에 runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation:false, capabilities.drop:ALL 적용 |
| kafka-exporter | danielqsj/kafka-exporter:v1.7.0 배포 — Consumer Lag·Broker 메트릭 Prometheus 수집 |
| NetworkPolicy 11-kafka-exporter | kafka-exporter 전용 정책 (monitoring→:9308, egress kafka:9092) |
| AlertManager Slack | #alerts-critical / #alerts-warning 수신 설정, webhook URL ESO 연동 |
| PrometheusRule 3종 | 서비스 안정성(8개)·보안(4개)·Kafka(4개) 알림 규칙 |
| Grafana 대시보드 3종 | Stability·Security·Kafka ConfigMap sidecar 자동 임포트 |
| ExchangeRate-API v6 마이그레이션 | 무료 v4 → 유료 v6 전환, API 키 Secrets Manager 관리, 70개 통화 수집 |
| Kafka 리스너 분리 (two-listener) | INTERNAL(pod IP:9093)/EXTERNAL(service-kafka:9092) 분리 — EKS hairpin routing 문제 해결 |
| NetworkPolicy 06-dataingestor 수정 | Aurora:3306·DocDB:27017·Redis:6379 egress 추가 |
| NetworkPolicy 07-kafka 수정 | inter-broker 통신용 pod CIDR:9093 egress 추가 |
| DB 초기화 Job 추가 | db-init-job.yaml — Aurora MySQL 스키마·통화 마스터(70개) 초기화 |
| Kafka 토픽 초기화 Job 추가 | kafka-init-job.yaml — 7개 토픽 생성 매니페스트 |
| init-db.sql PLN 추가 | currencies 마스터에 폴란드 즐로티 추가 |
| frontend 포트 수정 (80→8080) | nginx-unprivileged(uid 101)는 비특권 사용자라 :80 바인딩 불가(NET_BIND_SERVICE 없음). Deployment·Service·NetworkPolicy가 :80으로 설정되어 ALB→Pod 트래픽 차단(504). containerPort·targetPort·NetworkPolicy·probe 포트 모두 :8080으로 정정 |
| EKS 노드 SG 8080 inbound 추가 | ALB SG → EKS 노드 SG(식별자 비공개) TCP 8080 inbound 규칙 추가 — frontend 포트 8080 변경 후 ALB Target health 정상화 |
| NetworkPolicy ArgoCD 통합 (12개) | `k8s/overlays/eks/network-policies/kustomization.yaml` 생성, EKS overlay kustomization에 `- network-policies/` 추가 → 12개 NetworkPolicy 전체 ArgoCD 자동 관리 (기존 수동 kubectl apply 방식 대체) |
| ArgoCD ignoreDifferences 확장 | ConfigMap(MYSQL_HOST·MONGODB_HOST·REDIS_HOST), ExternalSecret(spec.dataFrom·spec.data·metadata.annotations), Deployment(kubectl.kubernetes.io/restartedAt) 3개 항목 추가 — phantom OutOfSync 및 rollout restart 무한 루프 해결 |
| ConfigMap base HOST 키 제거 | base/configmap.yaml에서 MYSQL_HOST·MONGODB_HOST·REDIS_HOST 삭제 → ArgoCD가 해당 필드를 소유하지 않아 sync 후에도 kubectl patch 값이 보존됨 (ServerSideApply 소유권 원리 적용) |
| metrics-server 설치 | 공식 컴포넌트 kubectl apply — HPA CPU/memory 메트릭 `<unknown>` 해결, ArgoCD HPA Degraded 상태 정상화 |
| sa-currency kustomization 수정 | `serviceaccount.yaml`이 currency-service kustomization.yaml resources 목록에서 누락 → sa-currency 미생성으로 service-currency Pod FailedCreate 발생 → 목록에 추가하여 해결 |
| EKS false positive 알림 제거 | kube-prometheus-stack values에 kubeControllerManager·kubeScheduler·kubeEtcd·kubeProxy `enabled: false` 추가 → EKS 관리형 컨트롤 플레인은 VPC에 미노출되므로 Prometheus 수집 불가 → KubeControllerManagerDown CRITICAL false positive 알림 제거 |
| service-ranking DocumentDB 전환 | DynamoDB Mock 제거, DocumentDB(motor) 직접 연결로 전환. country_clicks·click_history·ranking_results 컬렉션 사용 |
| ranking 스케줄러 버그 수정 | 자정 KST daily reset 시 Python logger.info() keyword argument 오류로 크래시 → f-string 임베드 방식으로 변경 |
| DynamoDBHelper 초기화 버그 수정 | `__init__`이 positional arg를 받지 않아 `DynamoDBHelper(table_name)` 호출 시 TypeError 발생 → `table_name: str = None` 파라미터 추가 |
| service-currency structlog 전환 | `logging.getLogger()` → `shared.logging.get_logger()` 교체 — Kafka 메시지 핸들러에서 structlog kwargs 사용 시 `Logger._log() got an unexpected keyword argument 'currency'` 오류 해결 |
| DocumentDB retryWrites=false | 전 서비스 MongoDB 연결 문자열에 `&retryWrites=false` 추가 (package-shared 5개 + mongodb_service.py 1개) — DocumentDB가 retryWrites 미지원(code 301)으로 ranking 클릭 시 500 오류 발생 해결 |
| PodNotReady 알림 CronJob 오탐 제거 | `prometheus-rules-stability.yaml` PodNotReady expr에 `unless on(pod,namespace) kube_pod_status_phase{phase="Succeeded"}==1` 추가 — 정상 완료된 dataingestor CronJob 파드가 5분마다 WARNING 알림 유발하던 오탐 해결 |
| TargetDown 알림 오탐 제거 | `kube-prometheus-stack-values.yaml` additionalScrapeConfigs에 `__meta_kubernetes_pod_phase drop Succeeded\|Failed` relabel 규칙 추가 — Completed 상태 파드(db-init, pln-insert, dataingestor-cronjob)를 스크레이프 대상에서 제외하여 TargetDown false positive 해결 |
| Security 대시보드 phase 쿼리 오류 수정 | `kube_pod_status_phase` 쿼리에 `== 1` 조건 누락 — phase 레이블만 필터하면 값 0인 시계열까지 집계되어 "Pending/Failed Pods"가 34, "Active Pods"가 실제보다 과다 표시되던 버그 수정 (`== 1` 및 `or vector(0)` 추가) |
